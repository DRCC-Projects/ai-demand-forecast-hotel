# Hotel Demand Forecasting System – End-to-End Build Plan
## Built with Claude Code on HP Victus (RTX 5050) | Zero Monthly Cost

---

## Architecture Overview

[Your Laptop] [Cloud Free Tiers]
───────────── ─────────────────
• SQLite (local DB) • GitHub Actions (scheduled scrapes, forecasts, alerts)
• GPU training (XGBoost/LSTM) • Hugging Face Spaces (model API)
• Manual weekly model update • Supabase (forecast cache, user auth)
• Vercel (React dashboard)
• Slack + Twilio (alerts)


**Data flow:**
- GitHub Actions scrapes events every 6h → stores in Supabase & local SQLite
- You run weekly GPU training on laptop → push model file to GitHub
- GitHub Actions loads model daily → generates forecasts → stores in Supabase
- Dashboard (Vercel) reads Supabase → shows GM
- Alerts trigger on high-impact events

---

## Week 0: Environment Setup (1 hour)

### Do this manually before prompting Claude

1. **Install Miniconda** – https://docs.conda.io
2. **Open Anaconda Prompt as Administrator** and run:
```bash
conda create -n hotel-forecast python=3.10 -y
conda activate hotel-forecast
conda install cudatoolkit=11.8 -c conda-forge -y
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install xgboost scikit-learn pandas numpy fastapi uvicorn prefect sqlalchemy supabase beautifulsoup4 requests selenium playwright google-cloud-bigquery python-dotenv
playwright install


3. Verify GPU:

python -c "import torch; print(torch.cuda.is_available())"
python -c "import xgboost; print(xgboost.build_info()['cuda_version'])"

4. Create free accounts:

    GitHub

    Supabase (https://supabase.com)

    Hugging Face (https://huggingface.co)

    Vercel (https://vercel.com)

    Slack (create workspace, get webhook URL)

    Twilio (trial account – ₹100 credit)

Get hotel data from GM – Excel file with columns: date, occupancy_pct, adr_inr, rooms_sold

Week 1: Project Scaffold + Local SQLite + Scraper

Copy this prompt to Claude Code:

Create a complete project structure for a hotel demand forecasting system. Use Python 3.10. Follow this structure:

hotel-forecast/
├── .env.example
├── .github/workflows/
│   ├── scrape.yml
│   ├── forecast.yml
│   └── alert.yml
├── data/
│   └── hotel.db (SQLite, created by scripts)
├── src/
│   ├── scraping/
│   │   ├── bookmyshow.py
│   │   ├── ktpo.py
│   │   └── run_all.py
│   ├── db/
│   │   ├── local_db.py (SQLAlchemy models for events, daily_metrics, features, forecasts)
│   │   └── supabase_client.py (push/pull from Supabase)
│   ├── features/
│   │   └── build_features.py
│   ├── models/
│   │   ├── train_local.py (GPU XGBoost)
│   │   └── predict.py
│   └── alerts/
│       └── send_alerts.py
├── requirements.txt
├── README.md
└── Makefile

Write the following files with full implementation:

1. `.env.example` – list all required env vars: SUPABASE_URL, SUPABASE_KEY, SLACK_WEBHOOK, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, TWILIO_WHATSAPP_TO, GOOGLE_APPLICATION_CREDENTIALS (optional)

2. `src/db/local_db.py` – SQLAlchemy models:
   - Event: id, name, start_date, end_date, venue, lat, lon, distance_km, attendance_tier, impact_score, source_url, scraped_at
   - DailyMetric: date, occupancy_pct, adr_inr, rooms_sold
   - Feature: date, day_of_week, is_weekend, is_holiday, event_count_7d, max_impact_score_7d, sum_impact_scores_7d, lag_1_occupancy, lag_7_occupancy, rolling_mean_7d_occupancy
   - Forecast: date, occupancy_pred, adr_pred, lower_bound, upper_bound, created_at
   Also include methods: init_db(), insert_events(), get_events_for_date_range(), etc.

3. `src/scraping/bookmyshow.py` – scraper for BookMyShow events in Whitefield, Bangalore. Use requests + BeautifulSoup. Extract event name, date, venue, and try to get attendee count from page text. Return list of dicts. Handle pagination. Add retries with tenacity.

4. `src/scraping/ktpo.py` – scrape KTPO convention center calendar (https://ktpo.in/events). Use requests + BeautifulSoup. Extract same fields.

5. `src/scraping/run_all.py` – orchestrate all scrapers, deduplicate events by name+date+venue, compute distance from hotel (12.9915, 77.7260) using haversine, assign attendance tier (small <500, medium 500-2000, large >2000), compute impact score using formula: (attendance_weight: small=0.2, medium=0.5, large=1.0) * (proximity_weight: <2km=1.0, 2-5km=0.7, 5-10km=0.4, >10km=0.1) * (duration_weight: 1 day=0.8, 2-3 days=1.0, 4+ days=1.2). Store events in local SQLite and also push to Supabase table 'events'. Use .env for credentials. Write logging to console.

6. `.github/workflows/scrape.yml` – GitHub Action that runs every 6 hours, checks out code, sets up Python, installs dependencies, runs `python src/scraping/run_all.py`. Use secrets for env vars. Also commits any changes to data/ folder (optional).

Provide the complete code for all files. Also write a `Makefile` with targets: init-db, scrape, train, forecast, serve-api.

Week 2: Historical Data Loading + Feature Engineering

Copy this prompt to Claude Code:

Continue building the hotel forecasting system. Now add:

1. A script `src/load_historical.py` that reads an Excel file (path passed as argument) with columns: date (YYYY-MM-DD), occupancy_pct (float 0-100), adr_inr (float), rooms_sold (int). The GM will provide this file. The script validates data, fills missing dates with nulls, and inserts into SQLite daily_metrics table. Also uploads to Supabase table daily_metrics.

2. A script `src/features/build_features.py` that:
   - Loads daily_metrics and events from SQLite
   - For each date in the date range (min date to today):
       - Compute day_of_week (0-6), is_weekend (5,6), is_holiday (load from a CSV data/india_holidays_2023_2025.csv – you can generate this file with known holidays or I'll provide later)
       - Aggregate events from 7 days before to 7 days after that date: event_count_7d, max_impact_score_7d, sum_impact_scores_7d
       - Add lag features: lag_1_occupancy, lag_7_occupancy, rolling_mean_7d_occupancy (using previous days' actual occupancy)
   - Store resulting features in SQLite table features and also upload to Supabase table features.
   - Use pandas for efficiency. Write unit tests for a few known dates.

3. A sample holidays CSV creator script `scripts/create_holidays.py` that generates a CSV with Indian national holidays + Karnataka state holidays for 2023-2026. Use known dates (Republic Day, Holi, Diwali, etc.) – just approximate. Provide the CSV file.

Provide all code. Also update the Makefile with targets: load-historical FILE=path/to/excel.xlsx, build-features, create-holidays.

Week 3: GPU Training Pipeline (XGBoost)

Copy this prompt to Claude Code:

Now implement the GPU-accelerated training pipeline. Write src/models/train_local.py with:

1. Load features from SQLite features table. Also load actual occupancy/adr from daily_metrics. Merge on date.
2. Define feature columns: all numeric columns except date and target. Drop any columns with >30% nulls. Impute remaining with median.
3. Split by time: train on dates before '2024-07-01' (or 80% of data), validation on dates after. Use TimeSeriesSplit from sklearn.
4. Train two XGBoost regressors:
   - occupancy_model – target = occupancy_pct
   - adr_model – target = adr_inr
   Use tree_method='gpu_hist', gpu_id=0, objective='reg:squarederror'. Tune hyperparameters with Hyperopt or GridSearchCV (limited search: max_depth, learning_rate, n_estimators, subsample). Use early stopping rounds=10.
5. Evaluate: compute MAE, MAPE, R2 on validation set. Print and log to training_log.csv.
6. Save models using XGBoost's native save_model('models/occupancy.ubj') and models/adr.ubj. Also save feature column list as models/feature_columns.pkl (list) and any imputer/scaler as models/preprocessor.pkl.
7. Add a function to generate a simple feature importance plot and save as models/feature_importance.png.
8. After training, automatically run a test prediction on next 30 days (using future events from SQLite) and store in data/sample_forecast.csv for quick inspection.

Write the script with argparse to allow override of train/test split date. Use logging. Add GPU availability check at start. Provide the full code.

Also add a GitHub Action .github/workflows/train.yml that is manually triggered (workflow_dispatch) and runs on ubuntu-latest (no GPU). Wait – we want to run on your laptop, not on GitHub. So instead, create a script scripts/upload_model.sh that commits and pushes the model files to GitHub after training. The training itself you run manually on your laptop. Provide that script too.

Update the Makefile with train target that runs python src/models/train_local.py.

Week 4: Model Evaluation & Optional LSTM

Copy this prompt to Claude Code:

Now add model evaluation and an optional LSTM baseline using PyTorch on your GPU.

1. Write src/models/evaluate.py that loads the trained XGBoost models, runs inference on the validation set (same split as training), and produces:
   - Scatter plot: actual vs predicted occupancy
   - Time series plot: actual vs predicted over validation period
   - Error distribution histogram
   - Table of metrics by month (to see seasonal performance)
   Saves plots to reports/ folder.

2. Write src/models/train_lstm.py (optional, only if you want to compare). This script:
   - Uses PyTorch with device='cuda'
   - Creates sequences of length 30 (past 30 days of features) to predict next day's occupancy
   - Builds a simple LSTM with 2 layers, hidden size 64
   - Trains for 100 epochs with early stopping
   - Saves model as models/lstm_occupancy.pt
   - Evaluates and compares against XGBoost
   - Note: This is CPU/GPU heavy but your RTX 5050 can handle it. Run only if XGBoost underperforms (MAPE >15%).

3. Add a script src/models/backtest.py that simulates how the model would have performed over the last 12 months using walk-forward validation (retrain each month). This gives a realistic estimate of real-world performance. Output a report to reports/backtest.html.

Provide all code. Update Makefile with evaluate, train-lstm, backtest.

Week 5: Model API & Hugging Face Deployment
Copy this prompt to Claude Code:

Now create a FastAPI server that serves the trained XGBoost models, and deploy it to Hugging Face Spaces (free tier).

1. Write src/api/server.py:
   - Loads models from models/ directory (occupancy.ubj, adr.ubj, feature_columns.pkl, preprocessor.pkl)
   - Defines endpoint POST /forecast expecting JSON: {"start_date": "2025-09-01", "end_date": "2025-09-30", "hotel_id": "whitefield"}
   - For each date in range:
       - Fetch events from SQLite (or Supabase if local not available) for that date ±7 days
       - Build feature vector using same logic as build_features.py
       - Apply preprocessor (imputation, scaling)
       - Predict occupancy and ADR
   - Returns list of daily forecasts with 90% confidence intervals (using quantile regression or bootstrap – implement simple bootstrap by adding noise to predictions)
   - Add caching: if same date range requested twice, return cached result (use functools.lru_cache with TTL of 1 hour)
   - Add health check endpoint GET /health
   - Use uvicorn to run

2. Write Dockerfile for the API:
   - FROM python:3.10-slim
   - Install system dependencies (gcc, libgomp1 for XGBoost)
   - Copy requirements.txt, install Python packages
   - Copy src/ and models/
   - Expose 7860
   - CMD uvicorn src.api.server:app --host 0.0.0.0 --port 7860

3. Create a Hugging Face Space (use 'Docker' SDK). Write a README.md for the Space that describes the API. Provide a sample curl command.

4. Write a script scripts/deploy_to_hf.py that uses huggingface_hub library to upload the Docker build context and trigger build. Use your HF token from env.

5. Update the Makefile with build-docker, run-api-local, deploy-hf.

Provide all files. Assume the model files are already in models/ from previous week.

Week 6: React Dashboard (Vercel)

Copy this prompt to Claude Code:

Build a React dashboard for the GM. Use Vite + TypeScript + TailwindCSS. Deploy to Vercel.

Project structure:
frontend/
├── src/
│   ├── components/
│   │   ├── EventCalendar.tsx (react-big-calendar)
│   │   ├── ForecastChart.tsx (recharts: line chart of forecast vs actual)
│   │   ├── ImpactList.tsx (table of upcoming events with impact scores)
│   │   ├── MissedRevenue.tsx (calculator: show revenue lost on past events)
│   │   └── AlertSettings.tsx (toggle alerts, thresholds)
│   ├── pages/
│   │   ├── Dashboard.tsx (main page)
│   │   ├── Login.tsx (Supabase auth)
│   │   └── Settings.tsx
│   ├── lib/
│   │   ├── supabaseClient.ts (initialize Supabase)
│   │   └── apiClient.ts (call HF Space forecast endpoint)
│   └── App.tsx
├── .env.example
├── package.json
└── vite.config.ts

Features:
- Supabase authentication (email/password) – free tier
- Dashboard after login shows:
  - Calendar view of upcoming events (color-coded by impact score)
  - Line chart: forecasted occupancy vs actual occupancy (actual entered manually via a form on the chart – GM can input daily actuals)
  - Table of next 30 days' forecasts with rate recommendations (if forecast occupancy >85%, recommend +20% ADR)
  - Missed revenue widget: for past events where actual occupancy exceeded forecast by >10%, calculate (actual_adr - recommended_adr) * rooms_sold
- Settings page: configure alert thresholds (e.g., alert when impact >0.7), WhatsApp number, Slack webhook
- All data read from Supabase tables (events, forecasts, daily_metrics). The API call to HF Space is only for on-demand 'what-if' scenarios.

Write the complete frontend code. Use React Query for data fetching. Use Zustand for global state (auth, user settings). Provide step-by-step deployment instructions for Vercel (connect GitHub, set env vars). Also provide a frontend/README.md for local development.

Important: The API endpoint for forecast is your Hugging Face Space URL. Provide a fallback mock data mode if API is unavailable.

Also write a script scripts/seed_supabase.py that populates Supabase with initial data (events from SQLite, forecasts from local model). This helps test the dashboard without waiting for GitHub Actions.

Provide all code and instructions.

Week 7: Alerts & Automation (GitHub Actions)

Copy this prompt to Claude Code:

Implement the alerting system and full GitHub Actions automation.

1. Write src/alerts/send_alerts.py:
   - Queries Supabase for events in next 7 days with impact_score > threshold (from settings table)
   - For each new event (not alerted before), send:
       - Slack message using webhook (rich formatting: event name, date, impact score, recommended rate increase)
       - WhatsApp message using Twilio API (sandbox for trial – format simple text)
   - Also check if forecast for next 7 days deviates >15% from baseline (e.g., seasonal average) – send a 'demand spike' alert even without events.
   - Record sent alerts in Supabase alerts table to avoid duplicates.

2. Create .github/workflows/alert.yml that runs daily at 8 AM IST. It runs python src/alerts/send_alerts.py. Use secrets for Slack webhook and Twilio credentials.

3. Create .github/workflows/forecast.yml that runs daily at 4 AM IST:
   - Checks out code
   - Installs dependencies
   - Runs python src/models/predict.py --start_date today --end_date +90days --output supabase
   - This script loads the latest model from models/ (committed in repo), fetches future events from Supabase, builds features, generates forecast, and upserts to Supabase forecasts table.
   - Model file is committed by you after weekly training. The workflow uses the latest commit.

4. Write src/models/predict.py as a standalone script with CLI arguments for date range and output (csv, supabase, or both). Use the same feature building logic as in the API.

5. Update the Makefile with forecast, send-alerts, run-forecast-workflow (for local testing).

6. Provide a scripts/setup_supabase.sql with the schema for all tables: events, daily_metrics, features, forecasts, alerts, settings, profiles (for auth). Use Supabase's SQL editor to run this.

Provide all code and SQL.

Week 8: Integration, Testing, Documentation, GM Demo

Copy this prompt to Claude Code:

Final week: integrate everything, write tests, and prepare for GM demo.

1. Write end-to-end test tests/test_e2e.py using pytest that:
   - Starts a local SQLite database
   - Inserts sample events and historical data
   - Runs feature building
   - Trains a tiny XGBoost model (with n_estimators=10 for speed)
   - Generates forecast
   - Calls the API (local) and checks response
   - Verifies alert script sends mock Slack/Twilio (use responses library to mock HTTP)
   - This test should pass in under 2 minutes on your laptop.

2. Write a docker-compose.yml that spins up:
   - Local Postgres (instead of SQLite for testing)
   - Local FastAPI (using your model)
   - A mock scraper that generates fake events
   - This is for GM to run a demo without cloud dependencies.

3. Write comprehensive README.md with:
   - System architecture diagram (ASCII or Mermaid)
   - Step-by-step setup for GM (how to get historical data, set up env vars, run local, access cloud dashboard)
   - Troubleshooting common issues (GPU not detected, scraping blocked, Twilio sandbox)
   - How to retrain model (weekly manual step)
   - Roadmap for future features (multi-hotel, real-time pricing)

4. Create a script scripts/gm_demo.py that simulates a 30-day forecast with fake events and shows before/after revenue impact. Run this for the GM during demo.

5. Provide a CONTRIBUTING.md for future developers (if you hire later).

6. Final checklist: all environment variables documented, all secrets stored in GitHub, Vercel deployment working, Supabase schema applied, Hugging Face Space API responding.

Provide all code, configs, and documentation.

Weekly Maintenance Workflow (After Build)
Day	Task	Where
Monday	Run make scrape manually (or let GitHub Actions do it)	Cloud
Tuesday	Check dashboard for new events	Browser
Wednesday	(If needed) Adjust impact score rules in run_all.py	Local
Thursday	Run make train (30 min on GPU) – retrain model with latest data	Laptop
Friday	git add models/ && git commit -m "weekly model update" && git push	Laptop
Saturday	Review alerts from Slack/WhatsApp	Phone
Sunday	Rest or tweak dashboard	-

Once a month: Review missed revenue report, show GM the impact.
Cost Summary (All Free Tiers)
Service	Free Limit	Your Usage	Cost
GitHub Actions	2,000 min/month	~15 min/day = 450 min/month	Free
Hugging Face Spaces	2 vCPU, 16 GB RAM	Your API uses <1%	Free
Vercel	100 GB bandwidth	Dashboard <1 GB/month	Free
Supabase	500 MB DB, 2 GB bandwidth	Events + forecasts <100 MB	Free
Twilio	Trial credit ₹100	WhatsApp alerts <₹10/month	~₹10
Slack	Free	Unlimited	Free

Total monthly: ₹0–₹20
Immediate Next Step

    Complete Week 0 setup (install software, create accounts, get hotel data)

    Copy the Week 1 prompt into Claude Code and run it in your project folder

    Follow weeks sequentially – each week's prompt builds on the previous

    If stuck, ask Claude: "I got error X when running Y. Help me fix it." Paste the error




	