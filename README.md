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
```

## Configuration

- **`.env`** — LM Studio connection settings
- **`config/career_pages.yaml`** — List of career page URLs to scrape

## Supported Career Platforms

| Platform | Mode | Notes |
|----------|------|-------|
| GitHub Careers | API | Page-based pagination |
| Amazon Jobs | API | Offset-based pagination |
| Microsoft Careers | API | Start-based pagination |
| Workday Sites (e.g. GEICO) | API | POST with JSON body |
| Any HTML career page | HTML + LLM | Requires LM Studio running |

## Output

Results are saved to `output/` as JSON, CSV, and HTML files.

## Agents

| Agent | LLM? | Purpose |
|-------|-------|---------|
| Planner | No | Loads career pages, creates scraping plan |
| Scraper | No | Fetches data from APIs or HTML pages |
| Parser | **Yes** | Extracts job listings from HTML content |
| Normalizer | Optional | Standardizes job data format (skippable) |
| Dedup | No | Removes duplicates and filters by date |
| Formatter | No | Saves final results to files |
