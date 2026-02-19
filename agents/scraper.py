"""
Scraper Agent — fetches job data from career pages.
Supports two modes:
  1. API mode — fetches structured JSON from known API endpoints
  2. HTML mode — fetches raw HTML and extracts text (fallback)
"""

from tools.web_scraper import fetch_page
from tools.text_extractor import extract_text, extract_job_links
from tools.api_fetcher import fetch_jobs_from_api, fetch_jobs_from_api_post, parse_github_careers_api, parse_amazon_jobs_api, parse_microsoft_jobs_api, parse_workday_jobs_api, parse_lever_jobs_api, parse_greenhouse_jobs_api
from models.state import AgentState


def scraper_agent(state: AgentState) -> dict:
    """
    Scrape the current page. Uses API if available, otherwise falls back to HTML scraping.
    """
    current_page = state.get("current_page", {})
    url = current_page.get("url", "")
    name = current_page.get("name", "Unknown")
    page_type = current_page.get("type", "career_page")
    api_url = current_page.get("api_url", "")
    keywords = current_page.get("keywords", "")

    if not url and not api_url:
        return {
            "raw_html": "",
            "cleaned_text": "",
            "extracted_jobs": [],
            "errors": [f"No URL found for page: {name}"],
        }

    # ── API Mode ─────────────────────────────────────────────────
    if page_type == "api" and api_url:
        print(f"[Scraper] 🔌 API mode for: {name}")
        print(f"[Scraper] Fetching: {api_url}")

        # Detect which API type we're dealing with
        is_amazon = "amazon.jobs" in api_url
        is_microsoft = "microsoft.com" in api_url
        is_workday = "myworkdayjobs.com" in api_url
        is_lever = "api.lever.co" in api_url
        is_greenhouse = "boards-api.greenhouse.io" in api_url

        # Fetch all pages from the API
        all_jobs = []

        if is_amazon:
            # Amazon uses offset-based pagination
            offset = 0
            limit = 10

            while True:
                params = {
                    "offset": offset,
                    "result_limit": limit,
                    "sort": "recent",
                    "category[]": "software-development",
                    "country[]": "USA",
                }

                result = fetch_jobs_from_api(api_url, params=params)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_hits = data.get("hits", 0)

                # Parse jobs from this page
                page_jobs = parse_amazon_jobs_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Offset {offset}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_hits})")

                # Check if we have all jobs
                if len(all_jobs) >= total_hits or len(page_jobs) == 0:
                    break

                if offset >= 500:  # Safety limit: max 500 jobs
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                offset += limit

        elif is_microsoft:
            # Microsoft uses start-based pagination with domain param
            start = 0
            page_size = 20

            while True:
                params = {
                    "domain": "microsoft.com",
                    "query": keywords or "Software Development",
                    "location": "United States, Multiple Locations, Multiple Locations",
                    "start": start,
                    "sort_by": "timestamp",
                    "filter_include_remote": "1",
                }

                result = fetch_jobs_from_api(api_url, params=params)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_count = data.get("data", {}).get("total", 0)
                positions = data.get("data", {}).get("positions", [])

                # Parse jobs from this page
                page_jobs = parse_microsoft_jobs_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Start {start}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                # Check if we have all jobs
                if len(all_jobs) >= total_count or len(positions) == 0:
                    break

                if start >= 500:  # Safety limit: max 500 jobs
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                start += len(positions)

        elif is_workday:
            # Workday uses POST with JSON body and offset-based pagination
            offset = 0
            limit = 20
            # Extract base URL for building job links (e.g. https://geico.wd1.myworkdayjobs.com/External)
            base_url = api_url.rsplit("/wday/", 1)[0] + "/" + api_url.split("/wday/cxs/")[1].split("/jobs")[0].split("/", 1)[1]

            while True:
                body = {
                    "limit": limit,
                    "offset": offset,
                    "searchText": keywords or "",
                }

                result = fetch_jobs_from_api_post(api_url, json_body=body)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_count = data.get("total", 0)

                # Parse jobs from this page
                page_jobs = parse_workday_jobs_api(data, name, base_url)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Offset {offset}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                # Check if we have all jobs
                if len(all_jobs) >= total_count or len(page_jobs) == 0:
                    break

                if offset >= 500:  # Safety limit: max 500 jobs
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                offset += limit

        elif is_lever:
            # Lever uses skip-based pagination
            skip = 0
            limit = 100

            while True:
                params = {"skip": skip, "limit": limit, "mode": "json"}

                result = fetch_jobs_from_api(api_url, params=params)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                # Lever returns a flat list
                if not isinstance(data, list):
                    data = []

                page_jobs = parse_lever_jobs_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Skip {skip}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)})")

                if len(page_jobs) < limit:
                    break

                if skip >= 500:  # Safety limit: max 500 jobs
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                skip += limit

        elif is_greenhouse:
            # Greenhouse uses page-based pagination
            page_num = 1

            while True:
                params = {"page": page_num}

                result = fetch_jobs_from_api(api_url, params=params)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_count = data.get("meta", {}).get("total", 0)

                page_jobs = parse_greenhouse_jobs_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Page {page_num}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                if len(page_jobs) == 0:
                    break

                if page_num >= 5:
                    print(f"[Scraper] Reached limit of 5 pages for {name}")
                    break

                page_num += 1

        else:
            # GitHub-style page-based pagination
            page_num = 1
            limit = 50

            while True:
                params = {
                    "page": page_num,
                    "limit": limit,
                    "sortBy": "posted_date",
                    "descending": "true",
                }
                if keywords:
                    params["keywords"] = keywords

                result = fetch_jobs_from_api(api_url, params=params)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_count = data.get("totalCount", 0)

                # Parse jobs from this page
                page_jobs = parse_github_careers_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Page {page_num}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                # Check if we have all jobs
                if len(all_jobs) >= total_count or len(page_jobs) == 0:
                    break

                if page_num >= 10:  # Safety limit: max 10 pages (500 jobs)
                    print(f"[Scraper] Reached limit of 10 pages for {name}")
                    break

                page_num += 1

        print(f"[Scraper] ✅ Fetched {len(all_jobs)} jobs from API")

        # In API mode, we skip the parser (no LLM needed!) and go straight
        # to normalizer. We put the parsed jobs directly into extracted_jobs.
        return {
            "raw_html": "",
            "cleaned_text": "",
            "extracted_jobs": all_jobs,
            "errors": [],
        }

    # ── HTML Scrape Mode ─────────────────────────────────────────
    print(f"[Scraper] 🌐 HTML mode for: {name} ({url})")

    result = fetch_page(url)

    if not result["success"]:
        print(f"[Scraper] Failed: {result['error']}")
        return {
            "raw_html": "",
            "cleaned_text": "",
            "errors": [f"Scraper failed for {name}: {result['error']}"],
        }

    raw_html = result["html"]
    print(f"[Scraper] Fetched {len(raw_html)} chars of HTML")

    # Extract clean text
    cleaned_text = extract_text(raw_html)
    print(f"[Scraper] Extracted {len(cleaned_text)} chars of text")

    # Extract job-related links for additional context
    job_links = extract_job_links(raw_html, url)
    if job_links:
        links_text = "\n\nJob-related links found on this page:\n"
        for link in job_links[:20]:
            links_text += f"- {link['text']}: {link['url']}\n"
        cleaned_text += links_text

    print(f"[Scraper] Found {len(job_links)} job-related links")

    return {
        "raw_html": raw_html,
        "cleaned_text": cleaned_text,
        "errors": [],
    }
