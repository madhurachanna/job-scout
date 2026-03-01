"""
Scraper Agent — fetches job data from career pages.
Supports two modes:
  1. API mode — fetches structured JSON from known API endpoints
  2. HTML mode — fetches raw HTML and extracts text (fallback)
"""

from tools.web_scraper import fetch_page
from tools.text_extractor import extract_text, extract_job_links
from tools.api_fetcher import fetch_jobs_from_api, fetch_jobs_from_api_post, parse_github_careers_api, parse_amazon_jobs_api, parse_eightfold_jobs_api, parse_workday_jobs_api, parse_lever_jobs_api, parse_greenhouse_jobs_api, parse_oracle_hcm_jobs_api, parse_phenom_jobs_api, parse_goldmansachs_jobs_api, parse_epam_jobs_api, fetch_apple_jobs, parse_apple_jobs_api, fetch_servicenow_jobs
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
        is_eightfold = "pcsx/search" in api_url
        is_workday = "myworkdayjobs.com" in api_url
        is_lever = "api.lever.co" in api_url
        is_greenhouse = "boards-api.greenhouse.io" in api_url
        is_oracle_hcm = "oraclecloud.com" in api_url
        is_phenom = "/widgets" in api_url
        is_goldman_sachs = "api-higher.gs.com" in api_url
        is_epam = "careers.epam.com" in api_url
        is_apple = "jobs.apple.com" in api_url
        is_servicenow = "careers.servicenow.com" in api_url

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

        elif is_eightfold:
            # Eightfold (pcsx/search) uses start-based pagination with domain param
            # Used by: Microsoft, Ford, and other Eightfold-powered career sites
            start = 0
            page_size = 20

            # Use domain from config, or extract from API URL as fallback
            eightfold_domain = current_page.get("domain", "")
            if not eightfold_domain:
                from urllib.parse import urlparse
                parsed = urlparse(api_url)
                eightfold_domain = parsed.hostname or ""

            # Extract base URL for job links
            from urllib.parse import urlparse as _urlparse
            _parsed = _urlparse(api_url)
            base_job_url = f"{_parsed.scheme}://{_parsed.hostname}"

            while True:
                params = {
                    "domain": eightfold_domain,
                    "query": keywords or "Software Engineer",
                    "location": "United States",
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
                page_jobs = parse_eightfold_jobs_api(data, name, base_job_url)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Start {start}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                # Check if we have all jobs (handle APIs that return total=0)
                if len(positions) == 0:
                    break

                if total_count > 0 and len(all_jobs) >= total_count:
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

        elif is_oracle_hcm:
            # Oracle Cloud HCM uses offset-based pagination with finder params
            offset = 0
            limit = 25

            # Extract base URL for building job links
            from urllib.parse import urlparse as _oracle_parse
            _op = _oracle_parse(api_url)
            oracle_base_url = f"{_op.scheme}://{_op.hostname}"

            # Get siteNumber from config (defaults to CX_1001)
            site_number = current_page.get("site_number", "CX_1001")

            while True:
                params = {
                    "onlyData": "true",
                    "expand": "requisitionList.secondaryLocations,flexFieldsFacet.values",
                    "finder": f"findReqs;siteNumber={site_number},facetsList=LOCATIONS;WORK_LOCATIONS;WORKPLACE_TYPES;TITLES;CATEGORIES;ORGANIZATIONS;UNPOSTING_DATE,limit={limit},offset={offset},keyword={keywords or 'software engineer'},sortBy=POSTING_DATES_DESC",
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
                items = data.get("items", [])
                total_count = items[0].get("TotalJobsCount", 0) if items else 0

                page_jobs = parse_oracle_hcm_jobs_api(data, name, oracle_base_url, site_number)

                all_jobs.extend(page_jobs)

                print(f"[Scraper] Offset {offset}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                if len(page_jobs) == 0 or len(all_jobs) >= total_count:
                    break

                if offset >= 500:  # Safety limit: max 500 jobs
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                offset += limit

        elif is_phenom:
            # Phenom People (used by Adobe) — POST with refineSearch body
            from_offset = 0
            page_size = 20

            from urllib.parse import urlparse as _phenom_parse
            _pp = _phenom_parse(api_url)
            base_url = f"{_pp.scheme}://{_pp.hostname}"

            # Read country filter from config or default to US
            country_filter = current_page.get("country", "United States of America")

            while True:
                body = {
                    "lang": "en_us",
                    "deviceType": "desktop",
                    "country": "us",
                    "pageName": "search-results",
                    "ddoKey": "refineSearch",
                    "sortBy": "",
                    "from": from_offset,
                    "jobs": True,
                    "counts": True,
                    "all_fields": ["category", "country", "state", "city", "type", "subtype"],
                    "size": page_size,
                    "clear498": False,
                    "jdsource": "facets",
                    "is498": True,
                    "keywords": keywords or "Software Engineer",
                    "global": True,
                    "selected_fields": {
                        "country": [country_filter]
                    },
                    "locationData": {},
                }

                result = fetch_jobs_from_api_post(
                    api_url, json_body=body,
                    headers={
                        "Referer": current_page.get("url", base_url),
                        "Origin": base_url,
                    }
                )

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_hits = data.get("refineSearch", {}).get("totalHits", 0)

                page_jobs = parse_phenom_jobs_api(data, name, base_url)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Offset {from_offset}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_hits})")

                if len(page_jobs) == 0 or len(all_jobs) >= total_hits:
                    break

                if from_offset >= 500:
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                from_offset += page_size

        elif is_goldman_sachs:
            # Goldman Sachs — GraphQL API with page-based pagination
            page_num = 0
            page_size = 20

            while True:
                body = {
                    "operationName": "GetRoles",
                    "variables": {
                        "searchQueryInput": {
                            "page": {"pageSize": page_size, "pageNumber": page_num},
                            "sort": {"sortStrategy": "POSTED_DATE", "sortOrder": "DESC"},
                            "filters": [],
                            "experiences": ["EARLY_CAREER", "PROFESSIONAL"],
                            "searchTerm": keywords or "Software Engineer",
                        }
                    },
                    "query": "query GetRoles($searchQueryInput: RoleSearchQueryInput!) { roleSearch(searchQueryInput: $searchQueryInput) { totalCount items { roleId corporateTitle jobTitle jobFunction locations { primary state country city __typename } status division skills jobType { code description __typename } externalSource { sourceId __typename } __typename } __typename } }",
                }

                result = fetch_jobs_from_api_post(
                    api_url, json_body=body,
                    headers={
                        "Origin": "https://higher.gs.com",
                        "Referer": "https://higher.gs.com/",
                    }
                )

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_count = data.get("data", {}).get("roleSearch", {}).get("totalCount", 0)

                page_jobs = parse_goldmansachs_jobs_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Page {page_num}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                if len(page_jobs) == 0 or (total_count > 0 and len(all_jobs) >= total_count):
                    break

                if len(all_jobs) >= 500:
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                page_num += 1

        elif is_epam:
            # EPAM Anywhere — custom REST API with x-anywhere-tenant header
            from_offset = 0
            page_size = 20

            epam_headers = {
                "x-anywhere-tenant": "anywhere",
            }

            while True:
                params = {
                    "q": keywords or "Software Engineer",
                    "facets": "country=4000602900000005338",
                    "from": from_offset,
                    "size": page_size,
                    "lang": "en",
                    "websiteLocale": "en-us",
                    "sortBy": "relevance;relocation=asc",
                }

                result = fetch_jobs_from_api(api_url, params=params, headers=epam_headers)

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

                page_jobs = parse_epam_jobs_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Offset {from_offset}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                if len(page_jobs) == 0 or (total_count > 0 and len(all_jobs) >= total_count):
                    break

                if from_offset >= 500:
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                from_offset += page_size

        elif is_apple:
            # Apple — custom API with CSRF token flow
            page_num = 1

            while True:
                result = fetch_apple_jobs(keywords=keywords or "Software Engineer", page=page_num)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"API fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                res = data.get("res", data)
                total_count = res.get("totalRecords", 0)

                page_jobs = parse_apple_jobs_api(data, name)
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Page {page_num}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                if len(page_jobs) == 0 or (total_count > 0 and len(all_jobs) >= total_count):
                    break

                if len(all_jobs) >= 500:
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
                    break

                page_num += 1

        elif is_servicenow:
            # ServiceNow — SSR HTML scraping with page-based pagination
            page_num = 1
            page_size = 20

            while True:
                result = fetch_servicenow_jobs(keywords=keywords or "Software Engineer", page=page_num, page_size=page_size)

                if not result["success"]:
                    print(f"[Scraper] API failed: {result['error']}")
                    return {
                        "raw_html": "",
                        "cleaned_text": "",
                        "extracted_jobs": [],
                        "errors": [f"Fetch failed for {name}: {result['error']}"],
                    }

                data = result["data"]
                total_count = data.get("total", 0)
                page_jobs = data.get("jobs", [])
                all_jobs.extend(page_jobs)

                print(f"[Scraper] Page {page_num}: fetched {len(page_jobs)} jobs (total so far: {len(all_jobs)}/{total_count})")

                if len(page_jobs) == 0 or (total_count > 0 and len(all_jobs) >= total_count):
                    break

                if len(all_jobs) >= 500:
                    print(f"[Scraper] Reached limit of 500 jobs for {name}")
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
    # ── Browser Mode (Playwright) ────────────────────────────────
    if page_type == "browser":
        print(f"[Scraper] 🌐 Browser mode for: {name}")
        from tools.browser_scraper import scrape_with_browser

        all_jobs = scrape_with_browser(url, name)
        print(f"[Scraper] ✅ Browser scraped {len(all_jobs)} jobs from {name}")

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
