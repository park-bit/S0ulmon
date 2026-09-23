# S0ulm0n Solar Aggregator

Multi-tenant solar monitoring and telemetry aggregation platform that bridges disparate inverter ecosystems. Combines real-time telemetry, power curves, and historical yield data from **SunSathi Solar (RENAC Power)** and **K Solar (Eybond SmartClient / ShineMonitor)** into a unified dashboard, automated reporting engine, and 90-day generation heatmap.

---

## Features

- **Multi-Source Aggregation**: Pulls and normalizes live output power, daily yield, monthly generation, and lifetime metrics across independent inverter platforms.
- **Provider Integrations**:
  - **SunSathi Solar (RENAC Power)**: Custom session authentication, MD5 request signature verification, live power metrics, and equipment telemetry.
  - **K Solar (Eybond SmartClient / ShineMonitor)**: Reverse-engineered HMAC-SHA1 salted authentication, encrypted query tokens, plant device status, and intraday yield.
- **Minimalist Real-Time Dashboard**: High-contrast dark theme with 6 core telemetry cards (Today Yield, Live Power, Month Yield, Lifetime Yield, CO2 Avoided, Inverter Health).
- **Interactive Visualizations**:
  - 7-Day stacked comparative yield chart powered by Chart.js.
  - Lazy-loaded 90-day calendar generation intensity heatmap with hover breakdowns.
- **Multi-Tenant Architecture**: User authentication via JWT, bcrypt salted password hashing, self-service inverter credentials configuration, and automated daily email reports.
- **Account Recovery**: OTP password reset flow using secure 6-digit tokens sent via SMTP.
- **Serverless Cloud Deployment**: Designed for zero-maintenance Vercel serverless execution with MongoDB Atlas persistence.

---

## Architecture

The system standardizes heterogeneous solar APIs into an extensible base model:

```
[SunSathi Solar / RENAC API]   ──> [RenacClient]       ──┐
                                                          ├──> [SolarAggregator] ──> [Normalized Unified Model]
[K Solar / ShineMonitor API]   ──> [ShineMonitorClient] ──┘                                   │
                                                                                              ├──> REST API (/api/stats, /api/heatmap)
                                                                                              ├──> Web Dashboard (HTML/CSS/JS)
                                                                                              └──> Scheduled Daily Email Reports
```

Each provider client inherits from `SolarProviderBase`, enforcing unified methods for authentication, live power polling, and historical yield queries. Adding a new inverter provider (e.g., Growatt, Solis, Enphase, SolarEdge) requires only implementing this abstract base class.

---

## Tech Stack

- **Backend**: Python 3.11+, Vercel Serverless Functions
- **Database**: MongoDB Atlas (`pymongo`)
- **Authentication**: JSON Web Tokens (`PyJWT`), `bcrypt`
- **Frontend**: Vanilla JavaScript, Semantic HTML5, Custom CSS
- **Charting**: Chart.js
- **Network & Cryptography**: `requests`, Python standard library `hmac`, `hashlib`, `smtplib`

---

## Project Structure

```
solar-aggregator/
├── api/                         # Vercel Serverless API Endpoints
│   ├── cron.py                  # Automated daily generation cron trigger
│   ├── forgot_password.py       # OTP generation and email dispatch
│   ├── heatmap.py               # 90-day lazy-loaded calendar heatmap data
│   ├── login.py                 # JWT authentication endpoint
│   ├── register.py              # User registration
│   ├── reset_password.py        # OTP verification and password update
│   ├── send_email.py            # On-demand email report dispatch
│   ├── settings.py              # Multi-tenant provider credential management
│   └── stats.py                 # Core telemetry aggregation endpoint
├── public/                      # Static Web Application
│   ├── app.js                   # Dashboard logic, charts, and lazy heatmap
│   ├── index.html               # Main telemetry dashboard
│   ├── login.html               # Authentication and OTP recovery views
│   ├── login.js                 # Auth form handlers
│   ├── settings.html            # User credentials and notifications UI
│   ├── settings.js              # Settings state manager
│   └── style.css                # Dark minimalist design system
├── src/                         # Core Python Library
│   ├── clients/                 # Inverter API clients
│   │   ├── base.py              # Abstract SolarProviderBase interface
│   │   ├── renac.py             # SunSathi Solar (RENAC) API client
│   │   └── shinemonitor.py      # K Solar (ShineMonitor) API client
│   ├── db.py                    # MongoDB connection helper
│   ├── models/                  # Pydantic data schemas
│   │   ├── renac.py             # RENAC API response schemas
│   │   └── shinemonitor.py      # ShineMonitor API response schemas
│   ├── services/
│   │   └── aggregator.py        # Normalization and multi-source aggregation
│   └── utils/
│       ├── crypto.py            # HMAC-SHA1 and MD5 signature algorithms
│       ├── logger.py            # Centralized logging
│       └── security.py          # Direct bcrypt password hashing helpers
├── vercel.json                  # Clean URL routing, build specs, and cron schedules
├── requirements.txt             # Pinned runtime dependencies
└── README.md
```

---

## Getting Started

### 1. Prerequisites

- Python 3.11 or higher
- MongoDB Atlas cluster URI
- Gmail account with an App Password (for OTP and email reports)

### 2. Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/park-bit/S0ulmon.git
cd S0ulmon/solar-aggregator
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # macOS/Linux
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the `solar-aggregator` root directory:

```env
# Database
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?appName=Cluster0

# Authentication
JWT_SECRET=your-random-32-character-secret

# Email Dispatch (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-character-app-password
```

### 4. Running Locally

You can test client connections and aggregation directly via Python:

```bash
python -m src.services.aggregator
```

To run the full stack locally with hot-reloading serverless endpoints and static assets, install the Vercel CLI:

```bash
npm install -g vercel
vercel dev
```

The application will be accessible at `http://localhost:3000`.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/register` | `POST` | Register a new user account |
| `/api/login` | `POST` | Authenticate user and receive JWT Bearer token |
| `/api/forgot_password` | `POST` | Request a 6-digit password reset OTP |
| `/api/reset_password` | `POST` | Verify OTP and reset password |
| `/api/settings` | `GET`, `POST` | Retrieve or update user inverter credentials |
| `/api/stats` | `GET` | Fetch normalized real-time telemetry and 7-day history |
| `/api/heatmap` | `GET` | Lazy load 90-day daily generation intensity records |
| `/api/send_email` | `POST` | Trigger an immediate generation report email |
| `/api/cron` | `GET` | Automated daily batch job for subscribed users |
