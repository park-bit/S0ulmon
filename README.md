# solar-aggregator

> Production-quality Python backend that aggregates solar generation data from **RENAC Power** and **ShineMonitor (Eybond SmartClient)** into a single unified output.

---

## Features

| Feature | Detail |
|---|---|
| **RENAC Power** | Full API: login, overview, storage, weather, chart, income, savings, device status |
| **ShineMonitor** | Full API: auth, plants info, plant detail, daily energy, PV charts, power curve, device status, meter, camera, warnings |
| **Common interface** | `SolarProviderBase` ABC — both clients are interchangeable |
| **Unified output** | Combined today/month/total generation + live power across both providers |
| **Resilience** | Tenacity exponential-backoff retries, 15 s timeout, auto token refresh |
| **Hosting** | Ready for Vercel Serverless deployments via `api/cron.py` and `vercel.json` |
| **Config** | pydantic-settings — all secrets from `.env`, never hardcoded |
| **Notifications** | Rule-based alerting via **WhatsApp (CallMeBot)**, Email, Telegram, Discord, and Loguru |

---

## Project Structure

```
solar-aggregator/
├── src/
│   ├── main.py                  # Entry point + scheduler
│   ├── config.py                # pydantic-settings config (all env vars)
│   ├── clients/
│   │   ├── base.py              # Abstract SolarProviderBase interface
│   │   ├── renac.py             # RENAC Power HTTP client
│   │   └── shinemonitor.py      # ShineMonitor HTTP client
│   ├── services/
│   │   ├── aggregator.py        # SolarAggregator — combines both providers
│   │   └── notifier.py          # Rule-based notification engine
│   ├── models/
│   │   ├── renac.py             # Pydantic v2 models for RENAC responses
│   │   └── shinemonitor.py      # Pydantic v2 models for ShineMonitor responses
│   └── utils/
│       ├── crypto.py            # MD5 (RENAC) + SHA1 (ShineMonitor) signing
│       ├── http.py              # Reusable HttpClient with retry + logging
│       └── logger.py            # Loguru bootstrap (single source of truth)
├── logs/                        # Auto-created; daily rotating log files
├── venv/                        # Python virtual environment
├── .env.example                 # Template — copy to .env and fill in values
├── requirements.txt             # Pinned runtime dependencies
└── README.md
```

---

## Quick Start

### 1. Clone and create the virtual environment

```bash
git clone <repo-url>
cd solar-aggregator
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

`.env` values you **must** fill in:

| Variable | Description |
|---|---|
| `RENAC_EMAIL` | RENAC account email |
| `RENAC_PASSWORD` | RENAC account password |
| `RENAC_STATION_ID` | Numeric station ID (verified default: `149199`) |
| `SHINEMONITOR_USERNAME` | ShineMonitor email |
| `SHINEMONITOR_PASSWORD` | ShineMonitor password |
| `SHINEMONITOR_COMPANY_KEY` | Company key (verified default: `bnrl_frRFjEz8Mkn`) |
| `SHINEMONITOR_PLANT_ID` | Plant identifier (verified default: `1301951`) |

Optional notification variables (leave blank to disable):

| Variable | Description |
|---|---|
| `SMTP_HOST` | SMTP server for email alerts |
| `SMTP_PORT` | SMTP port (default 587) |
| `SMTP_USERNAME` | SMTP auth username |
| `SMTP_PASSWORD` | SMTP auth password |
| `EMAIL_TO` | Alert recipient address |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Telegram chat/group ID |
| `DISCORD_WEBHOOK_URL` | Discord incoming webhook URL |

### Deployment

### Local Usage (Daemon)
```bash
python -m src.main
```
This will start the built-in scheduler (`schedule`) and poll the APIs every 15 minutes endlessly.

### Vercel Serverless
This project is configured out-of-the-box for **Vercel Serverless**.
1. Push the code to GitHub.
2. Import the project in Vercel.
3. Configure your Environment Variables in the Vercel Dashboard (copy from `.env`).
4. Set up a free cron job via `cron-job.org` pointing to `https://<your-vercel-domain>/api/cron`.

---

## Authentication

### RENAC Power

Verified base URL: `https://asia.renacpower.com:8084`

Every request carries three headers:

```
Token:     <session token from login — obtained automatically>
timestamp: <current Unix epoch>
sign:      MD5(email + password + timestamp).upper()
```

> **No `RENAC_APP_KEY` required.** The verified formula for `asia.renacpower.com:8084` uses only email, password, and timestamp. The sign is regenerated on **every request** (not once per session). Tokens are obtained and refreshed automatically — never stored in `.env`.

### ShineMonitor (Eybond SmartClient)

Verified base URL: `https://web.shinemonitor.com/public/`

**Login** (`action=auth`):
```
GET https://web.shinemonitor.com/public/?sign=<sign>&salt=<timestamp_ms>&action=auth&usr=<username>&company-key=<company_key>
```
The password is NOT sent. Instead, the `sign` is computed as:
```
sign = SHA1(salt + SHA1(password) + "&action=auth&usr=<usr>&company-key=<company-key>")
```
Returns `token` and `secret` valid for the `expire` duration.

**Subsequent requests**:
```
sign = SHA1(secret + token + "&action=<action>&param=val")
```
Every query must construct the URL exactly with `?sign=<sign>&salt=<salt>&token=<token>&action=<action>&param=val`.

**Generation Endpoints**:
* `queryTodayDevicePvCharts` provides daily energy.
* `queryPlantActiveOuputPowerOneDay` provides the active output power curve (live power).

---

## Aggregated Output Format

```json
{
  "renac": {
    "today_generation": 12.5,
    "month_generation": 320.1,
    "total_generation": 15400.0,
    "live_power": 4.2,
    "weather": { "temperature": 28.0, "wind_speed": 3.5 },
    "device_status": [ { "device_name": "Inverter 1", "status": 1 } ]
  },
  "shinemonitor": {
    "today_generation": 8.3,
    "month_generation": 210.7,
    "total_generation": 9800.0,
    "live_power": 2.8,
    "warnings": []
  },
  "combined": {
    "today_generation": 20.8,
    "month_generation": 530.8,
    "total_generation": 25200.0,
    "live_power": 7.0,
    "timestamp": "2024-01-15T10:30:00+00:00"
  },
  "errors": {
    "renac": null,
    "shinemonitor": null
  }
}
```

### Convenience methods

| Method | Returns |
|---|---|
| `get_today_summary()` | Per-provider + combined today generation |
| `get_live_summary()` | Per-provider + combined live power |
| `get_provider("renac")` | Raw normalised RENAC data |
| `get_provider("shinemonitor")` | Raw normalised ShineMonitor data |
| `get_combined_generation()` | Combined totals dict |

---

## Per-Module Self-Tests

Each module has a `if __name__ == "__main__"` block for standalone testing:

```bash
# Crypto primitives (no network, no .env needed)
python src/utils/crypto.py

# HTTP client (requires internet — uses httpbin.org)
python src/utils/http.py

# Config validation (requires .env)
python src/config.py

# RENAC client (requires .env + live credentials)
python src/clients/renac.py

# ShineMonitor client (requires .env + live credentials)
python src/clients/shinemonitor.py

# Aggregator (requires .env + live credentials)
python src/services/aggregator.py

# Notifier (mock data — no credentials needed)
python src/services/notifier.py
```

---

## Deployment on Render

1. Push to a GitHub/GitLab repo.
2. Create a **Background Worker** service on Render.
3. Set **Start Command**: `python -m src.main`
4. Add all `.env` variables as **Environment Variables** in Render's dashboard.
5. Set **Python version** to 3.12 in the runtime settings.

> Render automatically restarts the worker on crash; the scheduler will re-run login and resume polling.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `RENAC_BASE_URL` | `https://asia.renacpower.com:8084` | Verified RENAC API base URL |
| `RENAC_STATION_ID` | `149199` | RENAC station ID |
| `SHINEMONITOR_BASE_URL` | `https://web.shinemonitor.com/public/` | Verified ShineMonitor base URL |
| `SHINEMONITOR_COMPANY_KEY` | `bnrl_frRFjEz8Mkn` | ShineMonitor company key |
| `SHINEMONITOR_PLANT_ID` | `1301951` | ShineMonitor plant ID |
| `HTTP_TIMEOUT` | `15` | Request timeout (seconds) |
| `HTTP_MAX_RETRIES` | `3` | Retry attempts on server errors |
| `LOG_LEVEL` | `INFO` | Loguru level (`DEBUG`, `INFO`, etc.) |
| `POLL_INTERVAL_MINUTES` | `15` | How often to fetch data |
| `TIMEZONE` | `UTC` | IANA timezone for display/logging |

---

## Tech Stack

- **Python 3.12**
- **requests** — HTTP client
- **pydantic / pydantic-settings** — data validation + env config
- **tenacity** — retry logic
- **loguru** — structured logging
- **schedule** — in-process cron
- **python-dotenv** — `.env` loading
