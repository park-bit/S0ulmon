"""Cryptographic helpers used by both provider clients.

Provides:

* MD5 hex-digest (RENAC sign generation)
* SHA-1 hex-digest (ShineMonitor password hash & request signing)
* RENAC ``sign`` builder
* ShineMonitor ``sign`` builder

All functions are pure (no I/O, no side-effects) and fully type-hinted so they
are straightforward to unit-test.

Usage::

    from src.utils.crypto import renac_sign, sha1_hex, shinemonitor_sign
"""

import hashlib
import hmac
import time
from typing import Optional

__all__ = [
    "md5_hex",
    "sha1_hex",
    "renac_sign",
    "shinemonitor_passwd_hash",
    "shinemonitor_auth_sign",
    "shinemonitor_sign",
    "current_timestamp",
]


# ---------------------------------------------------------------------------
# Low-level primitives
# ---------------------------------------------------------------------------


def md5_hex(data: str, *, encoding: str = "utf-8") -> str:
    """Return the lowercase MD5 hex-digest of *data*.

    Args:
        data: The string to hash.
        encoding: Character encoding used when converting *data* to bytes.

    Returns:
        32-character lowercase hex string.
    """
    return hashlib.md5(data.encode(encoding)).hexdigest()


def sha1_hex(data: str, *, encoding: str = "utf-8") -> str:
    """Return the lowercase SHA-1 hex-digest of *data*.

    Args:
        data: The string to hash.
        encoding: Character encoding used when converting *data* to bytes.

    Returns:
        40-character lowercase hex string.
    """
    return hashlib.sha1(data.encode(encoding)).hexdigest()


def hmac_sha1_hex(key: str, data: str, *, encoding: str = "utf-8") -> str:
    """Return the lowercase HMAC-SHA1 hex-digest.

    Args:
        key: HMAC secret key string.
        data: The string to authenticate.
        encoding: Character encoding.

    Returns:
        40-character lowercase hex string.
    """
    return hmac.new(
        key.encode(encoding), data.encode(encoding), hashlib.sha1
    ).hexdigest()


def current_timestamp() -> int:
    """Return the current UTC Unix timestamp as an integer.

    Returns:
        Integer Unix epoch seconds.
    """
    return int(time.time())


# ---------------------------------------------------------------------------
# RENAC sign
# ---------------------------------------------------------------------------
# RENAC uses MD5-based request signing.
#
# Verified algorithm (reverse-engineered from asia.renacpower.com:8084):
#
#   payload = f"{app_key}{email}{password}{timestamp}"
#   sign    = MD5(payload).upper()
#
# For the verified production API (asia.renacpower.com:8084), ``app_key``
# is an empty string, reducing the formula to:
#
#   payload = f"{email}{password}{timestamp}"
#   sign    = MD5(payload).upper()
#
# ``app_key`` is kept as an optional parameter (default ``""``) for
# backwards compatibility and potential future API variants.
#
# The ``Token`` header carries the *login* token returned after authentication.
# The ``timestamp`` header carries the integer Unix epoch.
# The ``sign`` header carries the MD5 digest computed above.
# ---------------------------------------------------------------------------


def renac_sign(
    email: str,
    password: str,
    timestamp: Optional[int] = None,
    *,
    app_key: str = "",
) -> tuple[str, int]:
    """Build the RENAC API request signature.

    Computes ``sign = MD5(app_key + email + password + timestamp).upper()``.

    For the verified production API (``asia.renacpower.com:8084``) the
    ``app_key`` is an empty string, so callers can omit it entirely::

        sign, ts = renac_sign(email, password)

    Args:
        email: Authenticated user's e-mail address.
        password: Plaintext password (used only in sign computation).
        timestamp: Integer Unix epoch; defaults to ``current_timestamp()``.
        app_key: Optional RENAC application/secret key (default ``""``).
            Only needed if a future API variant requires one.

    Returns:
        A tuple of ``(sign_hex_upper, timestamp)`` ready to populate the
        ``sign`` and ``timestamp`` HTTP headers.
    """
    ts = timestamp if timestamp is not None else current_timestamp()
    payload = f"{app_key}{email}{password}{ts}"
    sign = md5_hex(payload).upper()
    return sign, ts


# ---------------------------------------------------------------------------
# ShineMonitor sign
# ---------------------------------------------------------------------------
# Reverse-engineered from https://www.shinemonitor.com/js/libhttp.js
#
# AUTH sign (action=auth):
#   action_fragment = f"&action=auth&usr={usr}&company-key={company_key}"
#   sign = SHA1(salt + SHA1(password) + action_fragment)
#   URL: GET /?sign=sign&salt=salt&action=auth&usr=usr&company-key=key&passwd=SHA1(pw)
#
# API sign (all other actions):
#   action_fragment = "&action=queryPlantsInfo" etc. (with URL-encoded special chars)
#   sign = SHA1(salt + secret + token + action_fragment)
#   URL: GET /?sign=sign&salt=salt&token=token&action=...&param=...
#
# The ``expire`` field is a Unix timestamp; tokens must be refreshed when
# ``current_time >= expire``.
# ---------------------------------------------------------------------------


def shinemonitor_passwd_hash(password: str) -> str:
    """Hash a plaintext password for ShineMonitor authentication.

    Args:
        password: Plaintext password string.

    Returns:
        Lowercase SHA-1 hex string of the password.
    """
    return sha1_hex(password)


def shinemonitor_auth_sign(
    salt: str,
    passwd_sha1: str,
    usr: str,
    company_key: str,
) -> str:
    """Build the ShineMonitor *authentication* request signature.

    Reverse-engineered from ``/js/libhttp.js``:

    .. code-block:: javascript

        var action = "&action=auth&usr=" + usr + "&company-key=" + company_key;
        var sign   = hex_sha1(salt + pwdSha1 + action);

    Args:
        salt: Millisecond Unix timestamp string.
        passwd_sha1: ``SHA1(password)`` — the hashed password.
        usr: ShineMonitor username (plain, no URL encoding needed for ASCII).
        company_key: Partner company key.

    Returns:
        Lowercase SHA-1 hex sign string.
    """
    action_fragment = f"&action=auth&usr={usr}&company-key={company_key}"
    payload = salt + passwd_sha1 + action_fragment
    return sha1_hex(payload)


def shinemonitor_sign(
    secret: str,
    token: str,
    action_fragment: str,
    salt: Optional[str] = None,
) -> tuple[str, str]:
    """Build the ShineMonitor per-request signature for non-auth API calls.

    Reverse-engineered from ``/js/libhttp.js``:

    .. code-block:: javascript

        var sign = hex_sha1(salt + currUsr.secret + currUsr.token + action);

    Args:
        secret: The session secret returned by the ``auth`` action.
        token: The session token returned by the ``auth`` action.
        action_fragment: Full query-string fragment for this request, e.g.
            ``"&action=queryPlantsInfo"`` or
            ``"&action=queryPlantInfo&plantid=1301951"``.  Special characters
            ``#``, ``'``, and spaces are URL-encoded per the JS source.
        salt: Pre-computed millisecond-precision timestamp string.  When
            ``None`` the salt is generated as ``str(int(time.time() * 1000))``.

    Returns:
        A tuple of ``(sign_hex, salt_str)``.
    """
    salt_str = salt if salt is not None else str(int(time.time() * 1000))
    # Mirror the JS: .replace(/#/g, "%23").replace(/'/g, "%27").replace(/ /g, '%20')
    encoded_action = (
        action_fragment
        .replace('#', '%23')
        .replace("'", '%27')
        .replace(' ', '%20')
    )
    payload = salt_str + secret + token + encoded_action
    sign = sha1_hex(payload)
    return sign, salt_str


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

