"""Notification service for solar-aggregator.

Provides rule-based alerting for notable events:

* Generation / power threshold crossed
* Provider errors
* Active device warnings from ShineMonitor

Channels supported:

* **Log** (always active — loguru WARNING)
* **Email / SMTP** (enabled when ``SMTP_HOST`` and ``EMAIL_TO`` are set)
* **Telegram** (enabled when ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` are set)
* **Discord** (enabled when ``DISCORD_WEBHOOK_URL`` is set)

Usage::

    from src.services.notifier import Notifier, ThresholdRule, default_notifier

    notifier = default_notifier()   # auto-wires channels from settings
    notifier.add_rule(ThresholdRule(
        name="low_power_alert",
        metric="combined.live_power",
        threshold=0.0,
        condition="equals",
        message="Live power dropped to zero — plant may be offline.",
    ))
    notifier.evaluate(aggregated_result)
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Any, Callable, Literal, Optional

import requests as _requests

from src.config import settings
from src.utils.logger import logger

__all__ = ["Notifier", "ThresholdRule", "ErrorRule", "WarningRule", "default_notifier"]

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

Condition = Literal["above", "below", "equals"]
NotifyCallback = Callable[[str, str, Any], None]


@dataclass
class ThresholdRule:
    """Fire when a numeric metric crosses a threshold.

    Args:
        name: Unique rule identifier.
        metric: Dot-path key into the aggregated result dict
            (e.g. ``"combined.live_power_kw"`` or ``"combined.today_generation_kwh"``).
        threshold: Numeric boundary value.
        condition: ``"above"`` | ``"below"`` | ``"equals"``.
        message: Human-readable alert message (shown in the notification).
        enabled: Set ``False`` to temporarily disable without removing.
    """

    name: str
    metric: str
    threshold: float
    condition: Condition
    message: str
    enabled: bool = True

    def evaluate(self, result: dict[str, Any]) -> Optional[str]:
        """Check the rule against *result*.

        Args:
            result: Full aggregated result dict from
                :meth:`SolarAggregator.fetch_all`.

        Returns:
            Alert message string if triggered, else ``None``.
        """
        if not self.enabled:
            return None

        # Support dot-path lookup: "combined.live_power_kw"
        value: Any = result
        try:
            for key in self.metric.split("."):
                value = value[key]
        except (KeyError, TypeError):
            logger.debug("ThresholdRule '{name}': metric '{metric}' not found.",
                         name=self.name, metric=self.metric)
            return None

        if not isinstance(value, (int, float)):
            return None

        triggered = (
            (self.condition == "above" and value > self.threshold)
            or (self.condition == "below" and value < self.threshold)
            or (self.condition == "equals" and value == self.threshold)
        )
        if triggered:
            return f"[{self.name}] {self.message} (value={value}, threshold={self.threshold})"
        return None


@dataclass
class ErrorRule:
    """Fire when a provider error is present in the result.

    Args:
        name: Unique rule identifier.
        provider: ``"renac"`` | ``"shinemonitor"`` | ``"any"``.
        message: Alert message prefix.
        enabled: Toggle for the rule.
    """

    name: str
    provider: str = "any"
    message: str = "Provider error detected."
    enabled: bool = True

    def evaluate(self, result: dict[str, Any]) -> Optional[str]:
        """Check for provider errors.

        Args:
            result: Full aggregated result dict.

        Returns:
            Alert message string if triggered, else ``None``.
        """
        if not self.enabled:
            return None

        errors: dict[str, Any] = result.get("errors", {})
        providers = (
            list(errors.keys()) if self.provider == "any" else [self.provider]
        )
        triggered_providers = [
            p for p in providers if errors.get(p) is not None
        ]
        if triggered_providers:
            details = "; ".join(
                f"{p}: {errors[p]}" for p in triggered_providers
            )
            return f"[{self.name}] {self.message} ({details})"
        return None


@dataclass
class WarningRule:
    """Fire when active ShineMonitor warnings are present.

    Args:
        name: Unique rule identifier.
        min_level: Minimum warning severity level (1=info, 2=warning, 3=fault).
        message: Alert message prefix.
        enabled: Toggle for the rule.
    """

    name: str
    min_level: int = 2
    message: str = "Active device warnings detected."
    enabled: bool = True

    def evaluate(self, result: dict[str, Any]) -> Optional[str]:
        """Check for active warnings above the severity threshold.

        Args:
            result: Full aggregated result dict.

        Returns:
            Alert message string if triggered, else ``None``.
        """
        if not self.enabled:
            return None

        warnings: list[dict[str, Any]] = (
            result.get("shinemonitor", {}).get("warnings", [])
        )
        severe = [
            w for w in warnings
            if isinstance(w.get("level"), int) and w["level"] >= self.min_level
        ]
        if severe:
            desc = "; ".join(
                w.get("warning_desc", "?") for w in severe[:5]
            )
            return (
                f"[{self.name}] {self.message} "
                f"({len(severe)} warning(s): {desc})"
            )
        return None


@dataclass
class DailySummaryRule:
    """Always fires to provide a daily summary of generation with a chart.
    
    Args:
        name: Unique rule identifier.
        message: Alert message prefix.
        enabled: Toggle for the rule.
    """
    
    name: str = "daily_summary"
    message: str = "☀️ Daily Solar Report"
    enabled: bool = True

    def evaluate(self, result: dict[str, Any]) -> Optional[str]:
        if not self.enabled:
            return None
            
        combined = result.get("combined", {})
        combined_today = combined.get("today_generation", 0.0)
        renac_today = result.get("renac", {}).get("today_generation", 0.0)
        shine_today = result.get("shinemonitor", {}).get("today_generation", 0.0)
        history = combined.get("history", {})
        
        # Format a clean message
        lines = [
            self.message,
            f"Total Generation: {combined_today:.2f} kWh",
            f"• Renac: {renac_today:.2f} kWh",
            f"• ShineMonitor: {shine_today:.2f} kWh"
        ]
        
        try:
            from src.services.charts import generate_weekly_trend_chart_url
            chart_url = generate_weekly_trend_chart_url(history)
            
            # We pass the chart URL via a special delimiter so the SMTP callback can embed it
            lines.append(f"\n[CHART_URL]{chart_url}[/CHART_URL]")
        except Exception as e:
            logger.warning("Failed to generate chart URL: {e}", e=e)
            
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Notifier
# ---------------------------------------------------------------------------


class Notifier:
    """Evaluates a set of rules against aggregated solar data and dispatches alerts.

    Args:
        callbacks: Optional list of callables invoked when a rule fires.
            Signature: ``callback(rule_name: str, alert_message: str, result: Any) -> None``.
            If empty, the default log-only callback is used.
    """

    def __init__(
        self,
        callbacks: Optional[list[NotifyCallback]] = None,
    ) -> None:
        self._rules: list[ThresholdRule | ErrorRule | WarningRule] = []
        self._callbacks: list[NotifyCallback] = callbacks or [_log_callback]

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: ThresholdRule | ErrorRule | WarningRule) -> None:
        """Register a notification rule.

        Args:
            rule: A :class:`ThresholdRule`, :class:`ErrorRule`, or
                :class:`WarningRule` instance.
        """
        self._rules.append(rule)
        logger.debug("Notifier: rule '{name}' added.", name=rule.name)

    def remove_rule(self, name: str) -> None:
        """Remove a rule by name.

        Args:
            name: The rule's ``name`` attribute.
        """
        self._rules = [r for r in self._rules if r.name != name]

    def add_callback(self, callback: NotifyCallback) -> None:
        """Register an additional notification callback.

        Args:
            callback: Callable with signature
                ``(rule_name, alert_message, result) -> None``.
        """
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, result: dict[str, Any]) -> list[str]:
        """Run all rules against *result* and dispatch alerts for triggered ones.

        Args:
            result: Full aggregated result dict from
                :meth:`SolarAggregator.fetch_all`.

        Returns:
            List of alert message strings that were triggered (may be empty).
        """
        triggered: list[str] = []
        for rule in self._rules:
            alert = rule.evaluate(result)
            if alert:
                triggered.append(alert)
                for cb in self._callbacks:
                    try:
                        cb(rule.name, alert, result)
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "Notifier callback error for rule '{r}': {exc}",
                            r=rule.name,
                            exc=exc,
                        )
        if not triggered:
            logger.debug("Notifier: no rules triggered.")
        return triggered

# ---------------------------------------------------------------------------
# Notification channel callbacks
# ---------------------------------------------------------------------------


def _smtp_callback(rule_name: str, alert: str, _result: Any) -> None:
    try:
        import re
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        
        # Extract chart URL if present
        chart_url = None
        match = re.search(r'\[CHART_URL\](.*?)\[/CHART_URL\]', alert)
        if match:
            chart_url = match.group(1)
            # Remove the tag from plain text version
            alert = alert.replace(match.group(0), f"📊 View Graph: {chart_url}")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[solar-aggregator] Alert: {rule_name}"
        msg["From"] = settings.smtp_username or "solar-aggregator@localhost"
        msg["To"] = settings.email_to  # type: ignore[assignment]

        # Plain text version
        part1 = MIMEText(alert, "plain", "utf-8")
        msg.attach(part1)

        # HTML version with embedded image
        if chart_url:
            html = f"""\
            <html>
              <head></head>
              <body>
                <p>{alert.replace(chr(10), '<br>')}</p>
                <img src="{chart_url}" alt="Solar Generation Chart" style="max-width:100%; height:auto;" />
              </body>
            </html>
            """
            part2 = MIMEText(html, "html", "utf-8")
            msg.attach(part2)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:  # type: ignore[arg-type]
            server.ehlo()
            server.starttls()
            server.ehlo()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(msg["From"], [settings.email_to], msg.as_string())

        logger.info("Email alert sent for rule '{r}' to {to}", r=rule_name, to=settings.email_to)
    except Exception as exc:  # noqa: BLE001
        logger.error("SMTP callback failed for rule '{r}': {exc}", r=rule_name, exc=exc)


def _telegram_callback(rule_name: str, alert: str, _result: Any) -> None:
    try:
        import re
        chart_url = None
        match = re.search(r'\[CHART_URL\](.*?)\[/CHART_URL\]', alert)
        if match:
            chart_url = match.group(1)
            alert = alert.replace(match.group(0), f"[📊 View Graph]({chart_url})")

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": settings.telegram_chat_id,
            "text": f"*solar-aggregator alert* \u2014 [{rule_name}]\n{alert}",
            "parse_mode": "Markdown",
        }
        resp = _requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        
        # Send chart as photo if present
        if chart_url:
            photo_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto"
            _requests.post(photo_url, json={"chat_id": settings.telegram_chat_id, "photo": chart_url}, timeout=10)

        logger.info("Telegram alert sent for rule '{r}'", r=rule_name)
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram callback failed for rule '{r}': {exc}", r=rule_name, exc=exc)


def _discord_callback(rule_name: str, alert: str, _result: Any) -> None:
    try:
        import re
        chart_url = None
        match = re.search(r'\[CHART_URL\](.*?)\[/CHART_URL\]', alert)
        if match:
            chart_url = match.group(1)
            alert = alert.replace(match.group(0), "")

        payload = {
            "embeds": [
                {
                    "title": f"solar-aggregator: {rule_name}",
                    "description": alert,
                    "color": 0xFF4444,  # red
                }
            ]
        }
        if chart_url:
            payload["embeds"][0]["image"] = {"url": chart_url}

        resp = _requests.post(settings.discord_webhook_url, json=payload, timeout=10)  # type: ignore[arg-type]
        resp.raise_for_status()
        logger.info("Discord alert sent for rule '{r}'", r=rule_name)
    except Exception as exc:  # noqa: BLE001
        logger.error("Discord callback failed for rule '{r}': {exc}", r=rule_name, exc=exc)


def _whatsapp_callback(rule_name: str, alert: str, _result: Any) -> None:
    try:
        import urllib.parse
        import re
        
        match = re.search(r'\[CHART_URL\](.*?)\[/CHART_URL\]', alert)
        if match:
            chart_url = match.group(1)
            alert = alert.replace(match.group(0), f"📊 View Graph: {chart_url}")

        msg = f"*solar-aggregator alert* \u2014 [{rule_name}]\n{alert}"
        encoded_msg = urllib.parse.quote(msg)
        url = f"https://api.callmebot.com/whatsapp.php?phone={settings.whatsapp_phone}&text={encoded_msg}&apikey={settings.whatsapp_api_key}"
        resp = _requests.get(url, timeout=10)
        resp.raise_for_status()
        logger.info("WhatsApp alert sent for rule '{r}'", r=rule_name)
    except Exception as exc:  # noqa: BLE001
        logger.error("WhatsApp callback failed for rule '{r}': {exc}", r=rule_name, exc=exc)


# ---------------------------------------------------------------------------
# Default callback (log-only)
# ---------------------------------------------------------------------------


def _log_callback(rule_name: str, alert: str, _result: Any) -> None:
    """Default callback — writes the alert to the log at WARNING level.

    Args:
        rule_name: Triggering rule identifier.
        alert: Full alert message string.
        _result: Aggregated result dict (unused by default callback).
    """
    import re
    match = re.search(r'\[CHART_URL\](.*?)\[/CHART_URL\]', alert)
    if match:
        chart_url = match.group(1)
        alert = alert.replace(match.group(0), f"📊 View Graph: {chart_url}")
    logger.warning("ALERT [{rule}]: {alert}", rule=rule_name, alert=alert)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------


def default_notifier() -> Notifier:
    """Build a :class:`Notifier` pre-loaded with sensible default rules.

    Automatically wires notification channels based on what is configured
    in the environment:

    * Log callback is **always** registered.
    * SMTP callback registered when ``SMTP_HOST`` and ``EMAIL_TO`` are set.
    * Telegram callback registered when ``TELEGRAM_BOT_TOKEN`` and
      ``TELEGRAM_CHAT_ID`` are set.
    * Discord callback registered when ``DISCORD_WEBHOOK_URL`` is set.

    Returns:
        Configured :class:`Notifier` instance with default rules.
    """
    notifier = Notifier()

    # Always register extra channels if configured
    if settings.email_notifications_enabled:
        notifier.add_callback(_smtp_callback)
        logger.info("Notifier: SMTP callback registered (to={to})", to=settings.email_to)
    if settings.telegram_notifications_enabled:
        notifier.add_callback(_telegram_callback)
        logger.info("Notifier: Telegram callback registered (chat={c})", c=settings.telegram_chat_id)
    if settings.discord_notifications_enabled:
        notifier.add_callback(_discord_callback)
        logger.info("Notifier: Discord callback registered")
    if settings.whatsapp_notifications_enabled:
        notifier.add_callback(_whatsapp_callback)
        logger.info("Notifier: WhatsApp callback registered (phone={p})", p=settings.whatsapp_phone)

    # Default rules
    notifier.add_rule(DailySummaryRule())
    notifier.add_rule(
        ErrorRule(
            name="provider_error",
            provider="any",
            message="One or more providers reported an error.",
        )
    )
    notifier.add_rule(
        WarningRule(
            name="device_warning",
            min_level=2,
            message="Active ShineMonitor device warnings detected.",
        )
    )
    return notifier


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    logger.info("=== Notifier self-test ===")

    # Simulate an aggregated result with an error and zero power
    mock_result: dict[str, Any] = {
        "renac": {"today_generation": 5.2, "live_power": 0.0},
        "shinemonitor": {
            "today_generation": 3.1,
            "live_power": 0.0,
            "warnings": [
                {"warning_desc": "Inverter overtemperature", "level": 3},
            ],
        },
        "combined": {
            "today_generation": 8.3,
            "live_power": 0.0,
        },
        "errors": {
            "renac": None,
            "shinemonitor": "Connection refused",
        },
    }

    notifier = default_notifier()
    alerts = notifier.evaluate(mock_result)
    print(f"\n{len(alerts)} alert(s) triggered:")
    for a in alerts:
        print(f"  - {a.encode('ascii', 'ignore').decode('ascii')}")

