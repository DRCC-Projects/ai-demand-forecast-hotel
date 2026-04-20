# Hotel Demand Forecasting System — PROJECT BRIEF
**Owner:** Ron | DRCC / StaxAI  
**Target client:** JW Marriott / Conrad / Angsana (Whitefield, Bengaluru)  
**Build machine:** HP Victus, RTX 5050  
**Last updated:** April 2026

---

## Mission

Build an AI-powered hotel demand forecasting system that tells the General Manager:
1. What occupancy and ADR to expect for the next 30–90 days
2. Which upcoming events (concerts, conferences, MICE) will drive demand spikes
3. What rate to charge on high-demand dates to maximise revenue

---

## Execution Strategy

### Two-phase approach. No parallelism.

```
Phase 1 (4 weeks) → GM Demo → Gate → Phase 2 (6 weeks)
```

**Gate condition:** GM provides a letter of intent, pays for pilot, or gives explicit sign-off to proceed.  
If gate is not cleared after Phase 1, the project pauses. 4 weeks lost, not 10.

---

## Phase 1 — MVP (4 Weeks)

**Goal:** Working demo URL to show the GM. Forecast accuracy > gut feel.

### Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.10 | |
| Local DB | SQLite | Zero setup, works offline |
| Cloud DB | **Neon.tech** (free Postgres) | Never auto-pauses, unlike Supabase free tier |
| Events data | **Ticketmaster Discovery API** | Free (5,000 req/day), JSON, legal, no JS rendering |
| ML model | XGBoost with `tree_method='gpu_hist'` | Handles tabular data well, fast on RTX 5050 |
| Serving | GitHub Actions daily job | No cold starts, no Docker, no HF Space |
| Dashboard | **Streamlit** (Streamlit Cloud, free) | Dashboard in days not weeks |
| Alerts | Slack webhook | Simple, free, reliable |
| Orchestration | GitHub Actions | Already in plan, proven approach |
| Secrets | GitHub repo secrets | |

### Pre-work (Before Week 1 — 2 hours)

> **This is the real gate before Phase 1.**

Open the GM's Excel file in a Jupyter notebook and:
1. Plot occupancy by month and day-of-week (bar charts)
2. Identify 3–5 known large events in the historical period
3. Check if occupancy was visibly higher on those dates vs. same weekday average
4. If yes → proceed. If no → have a conversation with GM before writing any code.

Script to run:
```bash
jupyter notebook  # or use VS Code notebooks
```

---

### Week 1 — Project Scaffold + Data Ingestion

**Goal:** SQLite DB working, historical hotel data loaded, Ticketmaster events pulling.

**Files to build:**
```
hotel-forecast/
├── .env.example
├── requirements.txt
├── Makefile
├── data/
│   └── hotel.db          # created by init_db()
├── src/
│   ├── db/
│   │   ├── local_db.py   # SQLAlchemy models
│   │   └── neon_client.py  # push/pull from Neon.tech
│   ├── ingest/
│   │   ├── load_historical.py   # reads GM's Excel file
│   │   └── ticketmaster.py      # Ticketmaster Discovery API
│   └── scraping/
│       └── ktpo.py              # KTPO convention centre (requests + BS4)
```

**SQLAlchemy models (local_db.py):**
- `Event`: id, name, start_date, end_date, venue, lat, lon, distance_km, attendance_tier, impact_score, source, scraped_at
- `DailyMetric`: date, occupancy_pct, adr_inr, rooms_sold
- `Feature`: date + all engineered columns
- `Forecast`: date, occupancy_pred, adr_pred, lower_bound, upper_bound, model_version, created_at

**Ticketmaster API (replace BookMyShow scraper):**
- Endpoint: `https://app.ticketmaster.com/discovery/v2/events.json`
- Params: `city=Bangalore`, `radius=15`, `unit=km`, `apikey=YOUR_KEY`
- Free tier: 5,000 requests/day. One call per 6h run = 4/day. Safe.
- Get API key: https://developer.ticketmaster.com/

**Impact score formula:**
```
impact_score = attendance_weight * proximity_weight * duration_weight

attendance_weight: small (<500) = 0.2, medium (500–2000) = 0.5, large (>2000) = 1.0
proximity_weight:  <2km = 1.0, 2–5km = 0.7, 5–10km = 0.4, >10km = 0.1
duration_weight:   1 day = 0.8, 2–3 days = 1.0, 4+ days = 1.2

Hotel coordinates: lat=12.9915, lon=77.7260 (update to actual hotel coordinates)
```

**Makefile targets:** `init-db`, `load-historical FILE=path.xlsx`, `scrape-events`

**Claude Code prompts for this week:**
1. "Create the project scaffold with SQLAlchemy models for Event, DailyMetric, Feature, Forecast in src/db/local_db.py. Use Python 3.10, SQLite via SQLAlchemy. Include init_db(), insert_events(), upsert_daily_metrics(). Handle all exceptions with logging. Write a smoke test at the bottom."
2. "Write src/ingest/ticketmaster.py that calls the Ticketmaster Discovery API for events within 15km of lat=12.9915, lon=77.7260. Parse event name, date, venue, attendance estimate. Compute haversine distance. Assign attendance tier and impact score using the formula in the brief. Return list of dicts. Add retries with tenacity. Log all HTTP calls."
3. "Write src/ingest/load_historical.py that reads an Excel file with columns: date, occupancy_pct, adr_inr, rooms_sold. Validate types. Fill missing dates with NaN. Upsert into SQLite daily_metrics table. Add argparse for file path."

---

### Week 2 — Feature Engineering + Holidays

**Goal:** Feature table populated, ready for model training.

**Files to build:**
```
├── data/
│   └── india_holidays_2023_2026.csv
├── scripts/
│   └── create_holidays.py
├── src/
│   └── features/
│       └── build_features.py
```

**Feature columns:**
```
date, day_of_week, is_weekend, is_holiday,
event_count_7d, max_impact_score_7d, sum_impact_scores_7d,
lag_1_occupancy, lag_7_occupancy, rolling_mean_7d_occupancy,
rolling_mean_30d_occupancy, days_to_next_event, days_since_last_event
```

**Key constraint:** Lag features require actual occupancy from previous days.  
For training: use historical `daily_metrics`.  
For live inference: lag values must be read from whatever actuals the GM has entered in the dashboard. If actuals are missing for N days, impute with rolling mean. **Document this fallback behaviour in code comments.**

**Holiday CSV columns:** `date, holiday_name, type` (type = national / karnataka / optional)

**Claude Code prompts:**
1. "Write scripts/create_holidays.py that generates data/india_holidays_2023_2026.csv with Indian national holidays and Karnataka state holidays for 2023–2026. Use known dates. Output CSV with columns: date (YYYY-MM-DD), holiday_name, type."
2. "Write src/features/build_features.py that loads daily_metrics and events from SQLite, engineers all feature columns listed in the brief, handles missing lag values by imputing with rolling mean, and upserts results into the features table. Use pandas. Add logging. Include a smoke test for 3 known dates."

---

### Week 3 — GPU Training + Predict Script

**Goal:** Trained model, daily forecast running locally.

**Files to build:**
```
├── models/               # gitignored initially
│   ├── occupancy.ubj
│   ├── adr.ubj
│   ├── feature_columns.pkl
│   └── preprocessor.pkl
├── src/
│   └── models/
│       ├── train_local.py
│       └── predict.py
├── scripts/
│   └── upload_model.sh   # pushes models to GitHub Releases
```

**Training notes:**
- Use `tree_method='gpu_hist'`, `gpu_id=0`
- Time-series split: train on all data before 2024-07-01, validate after
- Hyperparameter grid: `max_depth=[3,5,7]`, `learning_rate=[0.05,0.1]`, `n_estimators=[100,300]`, `subsample=[0.8,1.0]`
- Early stopping rounds: 15
- Save models with `save_model()` (native .ubj format)
- Log MAE, MAPE, R² to `reports/training_log.csv`
- After training, run predict for next 30 days and save to `data/sample_forecast.csv`

**Model versioning:** Store model files as `occupancy_YYYYMMDD.ubj`. `upload_model.sh` creates a GitHub Release with the date tag and uploads the files. `predict.py` downloads the latest release at runtime if models/ is empty.

**GPU check at script start:**
```python
import xgboost as xgb
import torch
assert torch.cuda.is_available(), "GPU not detected. Check CUDA drivers."
assert 'cuda' in xgb.build_info().get('USE_CUDA', '').lower() or \
       xgb.build_info().get('gpu_hist', False), "XGBoost GPU not available."
```

**Claude Code prompts:**
1. "Write src/models/train_local.py with GPU XGBoost training for occupancy_pct and adr_inr targets. Load features from SQLite. Time-series split. GridSearchCV on the grid in the brief. Early stopping=15. Save models and preprocessor. Log metrics. Auto-run 30-day sample forecast after training."
2. "Write src/models/predict.py with argparse: --start_date, --end_date, --output (csv|neon|both). Load model from models/ or GitHub Releases if missing. Build features using same logic as build_features.py. Predict occupancy and ADR. Generate 90% confidence interval using quantile regression (train a separate model with objective=reg:quantileerror at alpha=0.05 and 0.95). Upsert to Neon forecasts table."

---

### Week 4 — Streamlit Dashboard + Alerts + GitHub Actions Automation

**Goal:** Shareable URL for the GM. Slack alerts working. Full pipeline automated.

**Files to build:**
```
├── dashboard/
│   └── app.py            # Streamlit app
├── src/
│   └── alerts/
│       └── send_alerts.py
├── .github/
│   └── workflows/
│       ├── scrape.yml    # every 6h
│       ├── forecast.yml  # daily 4 AM IST
│       └── alert.yml     # daily 8 AM IST
├── scripts/
│   └── setup_neon.sql    # schema for all tables
```

**Dashboard pages (Streamlit):**
1. **Forecast view** — line chart: predicted occupancy vs actual (manual entry form), next 30 days table with rate recommendation (if predicted occupancy >85%, show +20% ADR)
2. **Events calendar** — table of upcoming events with impact scores, colour-coded high/medium/low
3. **Missed revenue** — for past periods where actual > forecast by >10%, show estimated revenue left on table

**Dead man's switch (add to alert.yml):**
```python
# In send_alerts.py: check pipeline health
last_scrape = neon.query("SELECT MAX(scraped_at) FROM events")[0][0]
if (datetime.now() - last_scrape).hours > 24:
    slack_alert("WARNING: Event scraper has not run in 24+ hours.")
```

**Actuals entry flow:** Dashboard has a simple date + occupancy form. On submit, upserts to `daily_metrics` table in Neon. `predict.py` reads from this table for lag features. Circle is closed.

**GitHub Actions timing (IST = UTC+5:30):**
```yaml
# scrape.yml:  cron: '30 0,6,12,18 * * *'  # 6:00, 12:00, 18:00, 00:00 IST
# forecast.yml: cron: '30 22 * * *'          # 4:00 AM IST
# alert.yml:    cron: '30 2 * * *'            # 8:00 AM IST
```

**Claude Code prompts:**
1. "Write dashboard/app.py as a Streamlit app with 3 pages: Forecast (line chart + rate recommendation table), Events (upcoming events by impact score), Missed Revenue (past revenue gap calculator). Read all data from Neon using psycopg2. Add a form to enter daily actual occupancy. Use st.cache_data with ttl=3600."
2. "Write src/alerts/send_alerts.py that queries Neon for events in next 7 days with impact_score > 0.6, sends a Slack webhook message for each new event (not previously alerted), and checks pipeline health (last scrape timestamp). Record sent alerts in Neon alerts table to avoid duplicates."
3. "Write .github/workflows/scrape.yml, forecast.yml, alert.yml. scrape runs every 6h, forecast at 4 AM IST, alert at 8 AM IST. Each workflow installs requirements.txt and runs the relevant script. Use GitHub secrets for NEON_DATABASE_URL, TICKETMASTER_API_KEY, SLACK_WEBHOOK_URL."

---

## Phase 2 — Full Product (6 Weeks, post-gate only)

Start only after GM validation.

### Stack upgrades
- Neon.tech → **Neon Pro** ($19/mo) or keep free tier if within limits
- Streamlit → **React + Vite + TypeScript + TailwindCSS** on Vercel
- Predict script → **FastAPI** on Railway or Render (not HF Space — cold start issue)
- Multi-hotel support → add `hotel_id` to all Neon tables

### Weeks 5–6: FastAPI + React Dashboard
- Build FastAPI first (2 weeks): `/forecast`, `/events`, `/metrics`, `/health` endpoints
- Then React (2 weeks): connect to FastAPI, implement all dashboard components
- Supabase Auth or Clerk for multi-tenant login

### Weeks 7–8: Model improvements + scalability
- Walk-forward backtest (`backtest.py`) to validate real-world accuracy
- Feature importance analysis + report generation (PDF for GM)
- Multi-hotel parameter config (each hotel has its own coordinates, impact scoring weights)
- White-label config: hotel logo, colour scheme via env vars

### Weeks 9–10: Polish + packaging
- Onboarding flow: GM uploads Excel → system auto-processes → dashboard live
- One-click deploy script for new hotel clients
- Pricing model: ₹8,000–15,000/month per hotel property

---

## Neon.tech Schema

```sql
-- Run this in Neon SQL editor before Week 1

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    start_date DATE,
    end_date DATE,
    venue TEXT,
    lat FLOAT,
    lon FLOAT,
    distance_km FLOAT,
    attendance_tier TEXT,  -- small, medium, large
    impact_score FLOAT,
    source TEXT,
    source_url TEXT,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(name, start_date, venue)
);

CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,
    occupancy_pct FLOAT,
    adr_inr FLOAT,
    rooms_sold INTEGER,
    entered_by TEXT DEFAULT 'gm',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE features (
    date DATE PRIMARY KEY,
    day_of_week INTEGER,
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    event_count_7d INTEGER,
    max_impact_score_7d FLOAT,
    sum_impact_scores_7d FLOAT,
    lag_1_occupancy FLOAT,
    lag_7_occupancy FLOAT,
    rolling_mean_7d_occupancy FLOAT,
    rolling_mean_30d_occupancy FLOAT,
    days_to_next_event INTEGER,
    days_since_last_event INTEGER,
    built_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE forecasts (
    date DATE PRIMARY KEY,
    occupancy_pred FLOAT,
    adr_pred FLOAT,
    lower_bound FLOAT,
    upper_bound FLOAT,
    model_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    alert_type TEXT,  -- event_spike, pipeline_failure, demand_spike
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    channel TEXT      -- slack, whatsapp
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Default settings
INSERT INTO settings VALUES ('alert_impact_threshold', '0.6', NOW());
INSERT INTO settings VALUES ('rate_increase_pct_high_demand', '20', NOW());
INSERT INTO settings VALUES ('high_demand_occupancy_threshold', '85', NOW());
```

---

## Environment Variables

```env
# Neon.tech
NEON_DATABASE_URL=postgresql://user:pass@host/dbname

# Ticketmaster
TICKETMASTER_API_KEY=your_key_here

# Alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
TWILIO_ACCOUNT_SID=optional
TWILIO_AUTH_TOKEN=optional
TWILIO_WHATSAPP_FROM=optional
TWILIO_WHATSAPP_TO=optional

# Model storage (Phase 1: GitHub Releases)
GITHUB_TOKEN=your_token_here
GITHUB_REPO=your_username/hotel-forecast

# Streamlit (Phase 1 only)
# Set these in Streamlit Cloud dashboard, not in .env
```

---

## Weekly Maintenance (Post-Build)

| Day | Task | Where |
|---|---|---|
| Mon | GitHub Actions auto-runs scrape | Cloud |
| Tue | Check dashboard for new high-impact events | Browser |
| Thu | `make train` — retrain XGBoost on GPU (20–30 min) | Laptop |
| Fri | `bash scripts/upload_model.sh` — push new model | Terminal |
| Sun | Review Slack alerts from week | Phone |
| Monthly | Show GM missed revenue report | Meeting |

---

## Cost Summary

| Service | Free Limit | Usage | Cost |
|---|---|---|---|
| Neon.tech | 512 MB, 3 GB transfer | <100 MB | Free |
| Streamlit Cloud | Unlimited public apps | 1 app | Free |
| GitHub Actions | 2,000 min/month | ~500 min/month | Free |
| Ticketmaster API | 5,000 req/day | 4 req/day | Free |
| Slack | Free tier | Unlimited | Free |
| Twilio WhatsApp | Trial ₹100 credit | Optional | ~₹10/mo |
| **Total** | | | **₹0–₹10/month** |

---

## How to Use This Brief with Claude Code

See the `CLAUDE_CODE_INSTRUCTIONS.md` file for step-by-step terminal commands.

---

*Built under DRCC / StaxAI branding. Colours: Navy #1A3A5C, Gold #C9A84C.*
