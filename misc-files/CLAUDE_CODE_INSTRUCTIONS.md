# How to Run This Project with Claude Code

## One-time setup

### 1. Install Claude Code
Open a terminal (PowerShell or Windows Terminal) and run:
```bash
npm install -g @anthropic-ai/claude-code
```
Requires Node.js 18+. Download from https://nodejs.org if not installed.

### 2. Create your project folder
```bash
mkdir hotel-forecast
cd hotel-forecast
```

### 3. Start Claude Code inside the project folder
```bash
claude
```
This opens an interactive terminal session. Claude Code can now read and write files in this folder.

---

## Week-by-week workflow

### How each week works

Every week, you:
1. Open a terminal in your project folder
2. Run `claude` to start a session
3. Paste one prompt at a time (from PROJECT_BRIEF.md)
4. Watch Claude write the code
5. Run the code, paste errors back if any
6. Move to the next prompt

### Week 1 — Session 1: Scaffold + DB models
Open terminal in `hotel-forecast/` folder:
```bash
claude
```
Then paste this prompt:
```
Create the project scaffold as described in PROJECT_BRIEF.md.
Start with requirements.txt, .env.example, Makefile, and 
src/db/local_db.py with SQLAlchemy models for Event, DailyMetric,
Feature, Forecast. Use Python 3.10, SQLite. Include init_db() and
upsert methods. Handle all exceptions with logging. Add a smoke
test at the bottom of local_db.py. Use the exact schema from the
PROJECT_BRIEF.md Neon schema section as reference for columns.
```

After Claude writes the files, test it:
```bash
python src/db/local_db.py
```

### Week 1 — Session 2: Ticketmaster ingest
In the same `claude` session (or start a new one):
```
Write src/ingest/ticketmaster.py. It should:
- Call Ticketmaster Discovery API for events within 15km of 
  lat=12.9915, lon=77.7260 (Whitefield, Bengaluru)
- Use API key from .env TICKETMASTER_API_KEY
- Parse: event name, start_date, end_date, venue, attendance estimate
- Compute haversine distance from hotel coordinates
- Assign attendance_tier (small/medium/large) and impact_score
  using the formula from PROJECT_BRIEF.md
- Return list of dicts, insert into SQLite via local_db.py
- Use tenacity for retries with exponential backoff
- Log all operations with timestamps
Add a __main__ block that runs a live test fetch and prints results.
```

Test it:
```bash
python src/ingest/ticketmaster.py
```

### Week 1 — Session 3: Historical data loader
```
Write src/ingest/load_historical.py. It should:
- Accept Excel file path as CLI argument (argparse)
- Read columns: date, occupancy_pct, adr_inr, rooms_sold
- Validate column types and date format
- Fill missing dates in range with NaN values
- Upsert into SQLite daily_metrics table via local_db.py
- Log row counts, date range, missing value count
Usage: python src/ingest/load_historical.py --file path/to/gm_data.xlsx
```

---

## Useful Claude Code commands during a session

| What you want | What to type |
|---|---|
| Fix an error | Paste the full error message and say "fix this" |
| See what files exist | `ls src/` or just ask Claude "what files have you created?" |
| Run a file | Exit claude (Ctrl+C), run in terminal, paste output back |
| Continue after a break | Start new session: `cd hotel-forecast && claude` |
| Ask Claude to review | "Review the code in src/db/local_db.py for bugs" |
| Add a feature | "Add X to the existing file Y" |

---

## Fixing errors — the workflow

When a script fails:
1. Copy the full terminal error output
2. Go back to Claude Code session
3. Type: `I got this error when running python src/ingest/ticketmaster.py:` then paste the error
4. Claude will fix it
5. Re-run the script

---

## Environment setup (do this once before Week 1)

```bash
# Create conda environment
conda create -n hotel-forecast python=3.10 -y
conda activate hotel-forecast

# Install CUDA XGBoost (for RTX 5050)
conda install cudatoolkit=11.8 -c conda-forge -y
pip install torch --index-url https://download.pytorch.org/whl/cu118
pip install xgboost scikit-learn pandas numpy

# Core packages
pip install fastapi uvicorn sqlalchemy psycopg2-binary
pip install requests beautifulsoup4 tenacity python-dotenv
pip install streamlit openpyxl xlrd haversine

# Verify GPU
python -c "import torch; print('GPU:', torch.cuda.is_available())"
python -c "import xgboost; print('XGB build:', xgboost.build_info())"
```

Create your `.env` file:
```bash
# In hotel-forecast folder, create .env:
NEON_DATABASE_URL=your_neon_connection_string
TICKETMASTER_API_KEY=your_key
SLACK_WEBHOOK_URL=your_webhook
```

---

## Accounts to create (before Week 1)

| Service | URL | What to get |
|---|---|---|
| Neon.tech | https://neon.tech | Free Postgres. Copy connection string. Run setup_neon.sql. |
| Ticketmaster Dev | https://developer.ticketmaster.com | Create app, copy API key |
| GitHub | https://github.com | Create repo `hotel-forecast`, copy GITHUB_TOKEN |
| Streamlit Cloud | https://streamlit.io/cloud | Connect GitHub repo in Week 4 |
| Slack | https://slack.com | Create workspace, create incoming webhook |

---

## Week 4: Deploying Streamlit dashboard

Once `dashboard/app.py` is working locally:
```bash
streamlit run dashboard/app.py
```

To deploy:
1. Push your repo to GitHub: `git push origin main`
2. Go to https://share.streamlit.io
3. Click "New app" → select your repo → set main file: `dashboard/app.py`
4. Add secrets (NEON_DATABASE_URL etc.) in the Streamlit secrets manager
5. Click Deploy → you get a public URL in 2–3 minutes

Share that URL with the GM for the demo.

---

## Git workflow (do this at end of each session)

```bash
git add .
git commit -m "Week 1: DB models and Ticketmaster ingest"
git push origin main
```

For model files after training (Week 3):
```bash
bash scripts/upload_model.sh   # uploads to GitHub Releases
```
Do NOT commit .ubj model files directly to the repo.

---

## Troubleshooting

**Claude Code says "no such file"**  
Make sure you ran `claude` from inside the `hotel-forecast/` folder, not from your home directory.

**GPU not detected**  
```bash
conda activate hotel-forecast
python -c "import torch; print(torch.cuda.is_available())"
# If False: reinstall torch with correct CUDA version for your driver
```

**Neon connection fails**  
Check that your NEON_DATABASE_URL in .env starts with `postgresql://` not `postgres://`.  
Neon requires SSL: add `?sslmode=require` at the end of the URL if not already there.

**Ticketmaster returns 0 events**  
Ticketmaster has limited India coverage. If no results, broaden search:
- Increase radius to 50km
- Remove city filter, use latlong + radius only
- Check API key is active at developer.ticketmaster.com

**Streamlit shows blank page**  
Check the app logs in Streamlit Cloud dashboard. Usually a missing secret or import error.
