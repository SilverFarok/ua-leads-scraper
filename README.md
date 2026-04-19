# UA Business Leads Dashboard MVP

Local lead scraping stack for Ukraine business contacts with:

- core pipeline in Python
- SQLite persistence
- discovery / enrichment / export split
- `.env` configuration
- local admin UI on top of the existing pipeline

The dashboard does not scrape by itself. It only stores campaign metadata, creates jobs, and starts background runs that call the existing core services.

## File Tree

```text
.
|-- .env.example
|-- README.md
|-- app.py
|-- config.py
|-- database.py
|-- main.py
|-- models.py
|-- requirements.txt
|-- dashboard
|   |-- __init__.py
|   |-- db
|   |   |-- __init__.py
|   |   |-- base.py
|   |   `-- session.py
|   |-- models
|   |   |-- __init__.py
|   |   |-- blacklist.py
|   |   |-- campaign.py
|   |   |-- run_job.py
|   |   `-- setting_profile.py
|   |-- repositories
|   |   |-- __init__.py
|   |   |-- blacklist.py
|   |   |-- campaigns.py
|   |   |-- runs.py
|   |   `-- settings_profiles.py
|   |-- routes
|   |   |-- __init__.py
|   |   |-- blacklist.py
|   |   |-- campaigns.py
|   |   |-- deps.py
|   |   |-- runs.py
|   |   `-- settings_profiles.py
|   |-- schemas
|   |   |-- __init__.py
|   |   `-- forms.py
|   |-- services
|   |   |-- __init__.py
|   |   |-- runtime_adapter.py
|   |   `-- view_models.py
|   `-- worker
|       |-- __init__.py
|       |-- job_manager.py
|       `-- job_runner.py
|-- data
|   |-- input.csv
|   |-- schema.sql
|   `-- ...
|-- exporters
|   |-- excel_exporter.py
|   |-- export_service.py
|   `-- google_sheets_exporter.py
|-- scrapers
|   |-- maps_scraper.py
|   |-- search_scraper.py
|   `-- site_scraper.py
|-- services
|   |-- discovery_service.py
|   `-- enrichment_service.py
|-- static
|   `-- style.css
|-- templates
|   |-- layout.html
|   |-- blacklist
|   |   `-- index.html
|   |-- campaigns
|   |   |-- detail.html
|   |   |-- list.html
|   |   `-- new.html
|   |-- runs
|   |   |-- _status.html
|   |   |-- detail.html
|   |   `-- list.html
|   `-- settings
|       `-- profiles.html
`-- utils
    |-- phone_utils.py
    `-- ...
```

## What the Core Pipeline Does

- reads `niche,city` pairs from CSV
- discovers companies through Google Maps and HTML search fallback
- enriches sites with contact extraction
- normalizes Ukrainian phone numbers to `+380XXXXXXXXX`
- classifies phones as `mobile`, `landline`, or `unknown`
- deduplicates and stores results in SQLite
- exports `full_results.xlsx` and `mobile_only.xlsx`
- can optionally sync the same data into Google Sheets

## What the Dashboard Adds

- campaigns
- setting profiles
- run jobs
- domain blacklist
- HTML pages with HTMX refresh for run status and logs

## Admin Tables and Init Logic

Admin metadata is stored separately from lead data.

Admin tables:

- `campaigns`
- `campaign_cities`
- `run_jobs`
- `setting_profiles`
- `domain_blacklist`

The dashboard schema is created automatically on app startup in `dashboard/db/session.py`:

- `AdminDatabase.init_db()` calls `AdminBase.metadata.create_all(...)`

The lead database schema is still created by the existing core `Database.init_db()` inside the runtime adapter when a job starts.

## Installation on Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
```

Edit `.env` if needed. Common values:

```env
INPUT_CSV=data/input.csv
DATABASE_PATH=data/leads.sqlite3
TARGET_MOBILE_LEADS=5000
MAX_SEARCH_RESULTS_PER_QUERY=30
MAX_SITE_PAGES_PER_COMPANY=3
ENRICHMENT_WORKERS=5
REQUEST_DELAY_SEC=1.5
REQUEST_TIMEOUT_SEC=20
BLOCKED_DOMAINS=
GOOGLE_SHEETS_ENABLED=false
GOOGLE_SHEETS_CREDENTIALS_PATH=data/google-service-account.json
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SHEETS_WORKSHEET_PREFIX=results
GOOGLE_SHEETS_CLEAR_BEFORE_WRITE=true
```

## Google Sheets Export Setup

The project now supports automatic Google Sheets export in both CLI runs and dashboard-triggered jobs.

Configuration is service-account based:

1. Create a Google Cloud project.
2. Enable Google Sheets API for that project.
3. Create a service account and download its JSON key.
4. Save the key locally, for example:

```text
data/google-service-account.json
```

5. Create or choose a Google Spreadsheet.
6. Share that spreadsheet with the service account email from the JSON key.
7. Put the spreadsheet ID and credentials path into `.env`:

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_CREDENTIALS_PATH=data/google-service-account.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_WORKSHEET_PREFIX=results
GOOGLE_SHEETS_CLEAR_BEFORE_WRITE=true
```

Behavior:

- CLI mode writes to worksheets:
  - `results_full`
  - `results_mobile`
- Dashboard campaign runs override the worksheet prefix automatically per campaign name, so each campaign gets its own pair of worksheets.
- Existing worksheets are reused and rewritten on every export.

## Running the Core CLI

```powershell
python main.py
python main.py --discover-only
python main.py --enrich-only
python main.py --export-only
```

## Running the FastAPI Dashboard

Start the local server:

```powershell
uvicorn app:app --reload
```

Then open:

- `http://127.0.0.1:8000/campaigns`

## Dashboard Pages

- `/campaigns`
- `/campaigns/new`
- `/campaigns/{id}`
- `/runs`
- `/runs/{id}`
- `/settings/profiles`
- `/blacklist`

## How Jobs Are Executed from the UI

1. Create a campaign in `/campaigns/new`.
2. The campaign stores:
   - niche
   - cities
   - target mobile leads
   - selected settings profile
   - default run mode
   - isolated SQLite path
   - isolated output directory
3. Click one of the run buttons on `/campaigns/{id}`:
   - `discover-only`
   - `enrich-only`
   - `full-run`
   - `export-only`
4. The UI creates a `run_jobs` row with status `queued`.
5. `/runs/{id}/start` asks the in-process `JobManager` to start a background thread.
6. The worker loads:
   - campaign
   - campaign cities
   - settings profile
   - blacklist domains
7. `PipelineAdapter` builds runtime settings and calls the existing core services:
   - `DiscoveryService`
   - `EnrichmentService`
   - `LeadExportService`
8. The worker updates `run_jobs` counters and appends logs into SQLite.
9. `/runs/{id}` refreshes status and logs via HTMX polling.

## Notes About Google Maps

Google Maps scraping remains the least stable part of the stack:

- selectors can break
- Google may rate-limit or interrupt sessions
- some businesses do not expose numbers on Maps

The current fallback path is:

1. Google Maps discovery via Playwright
2. HTML search discovery
3. site scraping for phone extraction

## Outputs

Per campaign, the runtime adapter writes:

- campaign-specific SQLite lead database
- campaign-specific Excel exports under the campaign output folder
- optional Google Sheets worksheets inside the configured spreadsheet

The admin dashboard itself stores metadata in:

- `data/admin.sqlite3`

## Basic Smoke Check

```powershell
python -m compileall app.py dashboard config.py database.py exporters services scrapers utils
```

If `fastapi` is installed, this should also import successfully:

```powershell
python -c "from app import app; print(app.title)"
```

## Phase 2 Improvements

- parallel discovery workers with better source partitioning
- resumable job queue with SQLite leasing and retry states
- richer blacklist and allowlist rules
- proxy support and browser fingerprint tuning
- captcha and interstitial handling
- campaign-level result browser and search UI
- Google Sheets sync
- authentication for multi-user local team access
