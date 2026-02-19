# Job Scout — Multi-Agent Job Scraper

A multi-agent system that fetches job postings from career pages and job portals using **LangGraph** for orchestration and **Qwen3 8B** (via LM Studio) as the LLM backbone.

## Architecture

```
Planner → Scraper → Parser (LLM) → Normalizer (LLM) → Dedup → Formatter
              ↑                                          │
              └──────── loop per career page ────────────┘
```

## Quick Start

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your LM Studio IP address

# 4. Add career pages to scrape
# Edit config/career_pages.yaml

# 5. Run
python run.py
```

## CLI Options

```bash
python run.py                          # Default run
python run.py --skip-normalization     # Skip LLM normalization (faster)
python run.py --output-dir results/    # Custom output directory
python run.py --config my_pages.yaml   # Custom config file
python run.py --schedule 60            # Run every 60 min (emails new jobs)
python run.py --notify-email you@x.com # Send results via email
python run.py --schedule 30 --notify-email you@x.com  # Full auto mode
```

## Configuration

- **`.env`** — LM Studio connection + SMTP email settings
- **`config/career_pages.yaml`** — List of career page URLs to scrape

## Supported Career Platforms

| Platform | Mode | API Type | Notes |
|----------|------|----------|-------|
| GitHub Careers | API | GET | JSON response |
| Amazon Jobs | API | GET | search.json endpoint |
| Microsoft Careers | API | GET | pcsx/search endpoint |
| GEICO (Workday) | API | POST | JSON body |
| Capital One (Workday) | API | POST | JSON body |
| Walmart (Workday) | API | POST | JSON body |
| Figma (Lever) | API | GET | Public postings API |
| Yelp (Lever) | API | GET | Public postings API |
| Twitch (Greenhouse) | API | GET | Job board API |
| GitLab (Greenhouse) | API | GET | Job board API |
| Pinterest (Greenhouse) | API | GET | Job board API |
| Cloudflare (Greenhouse) | API | GET | Job board API |
| Airbnb (Greenhouse) | API | GET | Job board API |
| Any HTML career page | HTML + LLM | — | Requires LM Studio |

### Adding More Sites

**Lever** — Any company using Lever: add `api.lever.co/v0/postings/{company-name}` to the config.

**Greenhouse** — Any company using Greenhouse: add `boards-api.greenhouse.io/v1/boards/{board-token}/jobs`.

**Workday** — Any company using Workday: add the `wday/cxs/.../jobs` endpoint.

## Scheduled Mode & Email Notifications

Run Job Scout on a schedule and get email alerts for new postings:

### Setup

1. Configure SMTP in `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   NOTIFY_EMAIL=your-email@gmail.com
   ```

2. For Gmail, create an [App Password](https://myaccount.google.com/apppasswords).

3. Run:
   ```bash
   python run.py --schedule 60 --notify-email you@gmail.com
   ```

### How It Works

- Each run scrapes all configured career pages (capped at 500 recent jobs per site)
- Results are stored in a local SQLite database (`data/job_scout.db`)
- Only **new** postings (not previously seen) are emailed
- The scheduler runs indefinitely until stopped with `Ctrl+C`

### AWS EC2 Deployment

```bash
# On EC2 (Ubuntu)
sudo apt update && sudo apt install python3-venv -y
git clone <your-repo> job-scout && cd job-scout
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env  # Configure SMTP

# Run in background
nohup python run.py --schedule 60 --notify-email you@gmail.com \
  --skip-normalization > job_scout.log 2>&1 &

# Check logs
tail -f job_scout.log
```

> **Tip:** Use `--skip-normalization` on EC2 if you don't have an LLM server running. All API-mode sites work without LLM.

## Output

Results are saved to `output/` as JSON, CSV, and HTML files. The HTML report features a beautiful dashboard with company filtering and "New Job" indicators.

## Agents

| Agent | LLM? | Purpose |
|-------|-------|---------| 
| Planner | No | Loads career pages, creates scraping plan |
| Scraper | No | Fetches data from APIs or HTML pages |
| Parser | **Yes** | Extracts job listings from HTML content |
| Normalizer | Optional | Standardizes job data format (skippable) |
| Dedup | No | Removes duplicates and filters by date |
| Formatter | No | Saves final results to files |
