"""
API Fetcher Tool — fetches job data from career site APIs.
Handles JSON API responses that return structured job data directly.
"""

import httpx
from config.settings import settings


# Known API patterns for popular career platforms
# Maps page type to API URL template
API_PATTERNS = {
    "github": {
        "base_url": "https://www.github.careers/api/jobs",
        "params_builder": lambda keywords, page, limit: {
            "keywords": keywords,
            "page": page,
            "limit": limit,
            "sortBy": "posted_date",
            "descending": "true",
        },
    },
}


def fetch_jobs_from_api(
    api_url: str,
    params: dict = None,
    timeout: int = None,
    headers: dict = None,
) -> dict:
    """
    Fetch jobs from a JSON API endpoint.

    Args:
        api_url: The API endpoint URL.
        params: Query parameters for the API call.
        timeout: Request timeout in seconds.
        headers: Optional extra headers to merge with defaults.

    Returns:
        dict with keys:
            - success (bool)
            - data (dict): Raw API response
            - error (str): Error message if failed
    """
    timeout = timeout or settings.request_timeout

    default_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",  # Exclude brotli to avoid decompressobj reuse bug
    }
    if headers:
        default_headers.update(headers)

    try:
        with httpx.Client(
            timeout=timeout,
            verify=False,
            follow_redirects=True,
            headers=default_headers,
        ) as client:
            resp = client.get(api_url, params=params or {})

            if resp.status_code == 200:
                return {
                    "success": True,
                    "data": resp.json(),
                    "error": "",
                }
            else:
                return {
                    "success": False,
                    "data": {},
                    "error": f"API returned HTTP {resp.status_code}",
                }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": str(e),
        }


def fetch_jobs_from_api_post(
    api_url: str,
    json_body: dict = None,
    timeout: int = None,
    headers: dict = None,
) -> dict:
    """
    Fetch jobs from a JSON API endpoint using POST.
    Used for Workday-style APIs that require POST with JSON body.
    """
    timeout = timeout or settings.request_timeout

    default_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if headers:
        default_headers.update(headers)

    try:
        with httpx.Client(
            timeout=timeout,
            verify=False,
            follow_redirects=True,
            headers=default_headers,
        ) as client:
            resp = client.post(api_url, json=json_body or {})

            if resp.status_code == 200:
                return {
                    "success": True,
                    "data": resp.json(),
                    "error": "",
                }
            else:
                return {
                    "success": False,
                    "data": {},
                    "error": f"API returned HTTP {resp.status_code}",
                }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": str(e),
        }


def parse_github_careers_api(api_response: dict, source_name: str) -> list[dict]:
    """
    Parse the GitHub Careers (Jibe/iCIMS) API response into job dicts.

    Args:
        api_response: Raw JSON response from the API.
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    raw_jobs = api_response.get("jobs", [])

    for raw_job in raw_jobs:
        data = raw_job.get("data", {})

        # Extract location from the description or city/state fields
        location = ""
        city = data.get("city", "")
        state = data.get("state", "")
        country = data.get("country", "")
        if city and state:
            location = f"{city}, {state}"
        elif city:
            location = city
        elif state:
            location = state

        # Try to get location from the description text
        if not location:
            desc = data.get("description", "")
            if "Remote" in desc:
                location = "Remote"
            elif "Locations" in desc:
                # Try to extract location from description
                import re
                loc_match = re.search(r"Locations?\s+(?:In this role you can work from\s+)?(.+?)(?:\s+Overview|\s+About)", desc)
                if loc_match:
                    location = loc_match.group(1).strip()

        # Build job URL
        slug = data.get("slug", "")
        job_url = f"https://www.github.careers/careers-home/jobs/{slug}" if slug else ""

        # Truncate description
        description = data.get("description", "")
        # Extract just the overview/summary part
        if "Overview" in description:
            overview_start = description.index("Overview") + len("Overview")
            # Find the next section header (Responsibilities, Qualifications, etc.)
            import re
            next_section = re.search(r"\s(Responsibilities|Qualifications|Requirements|About the role)", description[overview_start:])
            if next_section:
                description = description[overview_start:overview_start + next_section.start()].strip()
            else:
                description = description[overview_start:overview_start + 300].strip()
        else:
            description = description[:300].strip()

        jobs.append({
            "title": data.get("title", "Unknown"),
            "company": "GitHub",
            "location": location if location else "Not specified",
            "url": job_url,
            "description": description,
            "date_posted": data.get("posted_date", None),
            "source": source_name,
            "job_type": data.get("employment_type", "Full-time"),
        })

    return jobs


def parse_amazon_jobs_api(api_response: dict, source_name: str) -> list[dict]:
    """
    Parse the Amazon Jobs search.json API response into job dicts.

    Args:
        api_response: Raw JSON response from the Amazon search.json API.
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    raw_jobs = api_response.get("jobs", [])

    for raw_job in raw_jobs:
        # Filter to USA only (API may return international results)
        country_code = raw_job.get("country_code", "")
        if country_code != "USA":
            continue

        # Build location
        city = raw_job.get("city", "")
        state = raw_job.get("state", "")
        location = f"{city}, {state}" if city and state else city or state or "Not specified"

        # Build job URL
        job_path = raw_job.get("job_path", "")
        job_url = f"https://www.amazon.jobs{job_path}" if job_path else ""

        # Use short description
        description = raw_job.get("description_short", "")
        if not description:
            description = raw_job.get("description", "")[:300]

        # Parse posted date (format: "February 13, 2026")
        date_posted = raw_job.get("posted_date", "")
        if date_posted:
            try:
                from datetime import datetime
                dt = datetime.strptime(date_posted, "%B %d, %Y")
                date_posted = dt.strftime("%Y-%m-%dT00:00:00+0000")
            except (ValueError, TypeError):
                date_posted = ""

        jobs.append({
            "title": raw_job.get("title", "Unknown"),
            "company": "Amazon",
            "location": location,
            "url": job_url,
            "description": description,
            "date_posted": date_posted,
            "source": source_name,
            "job_type": raw_job.get("job_schedule_type", "Full-time").capitalize(),
        })

    return jobs


def parse_eightfold_jobs_api(api_response: dict, source_name: str, base_url: str = "") -> list[dict]:
    """
    Parse an Eightfold pcsx/search API response into job dicts.

    Used by: Microsoft, Ford, and other Eightfold-powered career sites.

    Args:
        api_response: Raw JSON response from the Eightfold search API.
        source_name: Name of the source for attribution.
        base_url: Base URL for building job links (e.g. "https://jobs.ford.com").

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    data = api_response.get("data", {})
    raw_jobs = data.get("positions", [])

    # Derive company name from source_name (e.g. "Ford Careers" -> "Ford")
    company = source_name.replace(" Careers", "").replace(" Jobs", "")

    for raw_job in raw_jobs:
        # Build location from locations array
        locations = raw_job.get("locations", [])
        location = ", ".join(locations) if locations else "Not specified"

        # Build job URL
        position_url = raw_job.get("positionUrl", "")
        job_url = f"{base_url}{position_url}" if position_url and base_url else ""

        # Parse posted timestamp (Unix seconds)
        date_posted = ""
        posted_ts = raw_job.get("postedTs")
        if posted_ts:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(posted_ts, tz=timezone.utc)
                date_posted = dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
            except (ValueError, TypeError, OSError):
                pass

        # Get display job ID for reference
        display_id = raw_job.get("displayJobId", "")
        department = raw_job.get("department", "")
        description = f"{department}" if department else ""
        if display_id:
            description = f"Job ID: {display_id}" + (f" | {department}" if department else "")

        jobs.append({
            "title": raw_job.get("name", "Unknown"),
            "company": company,
            "location": location,
            "url": job_url,
            "description": description,
            "date_posted": date_posted,
            "source": source_name,
            "job_type": "Full-time",
        })

    return jobs


def parse_workday_jobs_api(api_response: dict, source_name: str, base_url: str) -> list[dict]:
    """
    Parse a Workday /wday/cxs/.../jobs API response into job dicts.

    Args:
        api_response: Raw JSON response from the Workday API.
        source_name: Name of the source for attribution.
        base_url: Base URL for building job links (e.g. https://geico.wd1.myworkdayjobs.com/External).

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    raw_jobs = api_response.get("jobPostings", [])

    for raw_job in raw_jobs:
        # Build location
        location = raw_job.get("locationsText", "Not specified")

        # Build job URL from external path
        external_path = raw_job.get("externalPath", "")
        job_url = f"{base_url}{external_path}" if external_path else ""

        # Parse posted date text (e.g., "Posted 4 Days Ago", "Posted Today", "Posted 30+ Days Ago")
        date_posted = ""
        posted_on = raw_job.get("postedOn", "")
        if posted_on:
            try:
                from datetime import datetime, timedelta, timezone
                import re
                days_match = re.search(r"(\d+)\+?\s*Days?", posted_on)
                if "Today" in posted_on:
                    dt = datetime.now(timezone.utc)
                    date_posted = dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
                elif "Yesterday" in posted_on:
                    dt = datetime.now(timezone.utc) - timedelta(days=1)
                    date_posted = dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
                elif days_match:
                    days_ago = int(days_match.group(1))
                    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
                    date_posted = dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
            except (ValueError, TypeError):
                pass

        # Derive company name from source_name (e.g. "Geico Careers" -> "Geico")
        company = source_name.replace(" Careers", "").replace(" Jobs", "")

        jobs.append({
            "title": raw_job.get("title", "Unknown"),
            "company": company,
            "location": location,
            "url": job_url,
            "description": raw_job.get("bulletFields", [""])[0] if raw_job.get("bulletFields") else "",
            "date_posted": date_posted,
            "source": source_name,
            "job_type": "Full-time",
        })

    return jobs


def parse_lever_jobs_api(api_response: list, source_name: str) -> list[dict]:
    """
    Parse the Lever Postings API response into job dicts.

    Lever returns a flat JSON array of posting objects.
    Endpoint: GET https://api.lever.co/v0/postings/{company}

    Args:
        api_response: Raw JSON response (list of posting dicts).
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    for raw_job in api_response:
        # Build location from categories
        categories = raw_job.get("categories", {})
        location = categories.get("location", "Not specified")
        department = categories.get("department", "")
        team = categories.get("team", "")
        commitment = categories.get("commitment", "Full-time")

        # Build job URL
        job_url = raw_job.get("hostedUrl", "")

        # Parse created timestamp (Unix milliseconds)
        date_posted = ""
        created_at = raw_job.get("createdAt")
        if created_at:
            try:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
                date_posted = dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
            except (ValueError, TypeError, OSError):
                pass

        # Extract company name from the first part of source_name
        # or use the text field
        company = source_name.replace(" Jobs", "").replace(" Careers", "")

        # Description: combine description lists if available
        desc_plain = raw_job.get("descriptionPlain", "")
        if desc_plain:
            description = desc_plain[:300].strip()
        else:
            description = raw_job.get("text", "")

        jobs.append({
            "title": raw_job.get("text", "Unknown"),
            "company": company,
            "location": location,
            "url": job_url,
            "description": description,
            "date_posted": date_posted,
            "source": source_name,
            "job_type": commitment if commitment else "Full-time",
        })

    return jobs


def parse_greenhouse_jobs_api(api_response: dict, source_name: str) -> list[dict]:
    """
    Parse the Greenhouse Job Board API response into job dicts.

    Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs

    Args:
        api_response: Raw JSON response from the Greenhouse API.
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    raw_jobs = api_response.get("jobs", [])

    for raw_job in raw_jobs:
        # Build location
        location_obj = raw_job.get("location", {})
        location = location_obj.get("name", "Not specified") if location_obj else "Not specified"

        # Build job URL
        job_url = raw_job.get("absolute_url", "")

        # Use updated_at as an approximate posted date, capped at 60 days
        # to avoid showing long-stale listings as if they were recently posted.
        date_posted = ""
        updated_at = raw_job.get("updated_at", "")
        if updated_at:
            try:
                from datetime import timedelta, timezone as _tz
                dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                # Only use if updated within the last 60 days
                if (datetime.now(_tz.utc) - dt).days <= 60:
                    date_posted = dt.strftime("%Y-%m-%dT%H:%M:%S+0000")
            except (ValueError, TypeError):
                pass

        # Extract company name from source_name
        company = source_name.replace(" Careers", "").replace(" Jobs", "")

        # Departments
        departments = raw_job.get("departments", [])
        dept_names = [d.get("name", "") for d in departments if d.get("name")]

        # Description — metadata only since full content requires per-job fetch
        description = ", ".join(dept_names) if dept_names else ""

        jobs.append({
            "title": raw_job.get("title", "Unknown"),
            "company": company,
            "location": location,
            "url": job_url,
            "description": description,
            "date_posted": date_posted,
            "source": source_name,
            "job_type": "Full-time",
        })

    return jobs



def parse_oracle_hcm_jobs_api(api_response: dict, source_name: str, base_url: str = "", site_number: str = "CX_1001") -> list[dict]:
    """
    Parse an Oracle Cloud HCM recruitingCEJobRequisitions API response into job dicts.

    Used by: JPMorgan Chase, Oracle, and other Oracle Cloud HCM sites.
    The API returns nested JSON with items[0].requisitionList containing job objects.

    Args:
        api_response: Raw JSON response from the Oracle HCM API.
        base_url: Base URL for building job links (e.g. "https://eeho.fa.us2.oraclecloud.com").
        source_name: Name of the source for attribution.
        site_number: Oracle HCM site number for building job URLs.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    items = api_response.get("items", [])
    if not items:
        return jobs

    search_item = items[0]
    raw_jobs = search_item.get("requisitionList", [])

    for raw_job in raw_jobs:
        # Filter to US jobs only
        country = raw_job.get("PrimaryLocationCountry", "")
        if country and country != "US":
            continue

        title = raw_job.get("Title", "Unknown")
        location = raw_job.get("PrimaryLocation", "Not specified")

        # Build job URL
        job_id = raw_job.get("Id", "")
        job_url = f"{base_url}/hcmUI/CandidateExperience/en/sites/{site_number}/job/{job_id}" if job_id and base_url else ""

        # Parse posted date (format: "2026-02-24")
        date_posted = ""
        posted_date = raw_job.get("PostedDate", "")
        if posted_date:
            try:
                from datetime import datetime
                dt = datetime.strptime(posted_date, "%Y-%m-%d")
                date_posted = dt.strftime("%Y-%m-%dT00:00:00+0000")
            except (ValueError, TypeError):
                date_posted = ""

        description = raw_job.get("ShortDescriptionStr", "")

        # Extract company name from source_name
        company = source_name.replace(" Careers", "").replace(" Jobs", "")

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": job_url,
            "description": description,
            "date_posted": date_posted,
            "source": source_name,
            "job_type": "Full-time",
        })

    return jobs


def parse_phenom_jobs_api(api_response: dict, source_name: str, base_url: str = "") -> list[dict]:
    """
    Parse a Phenom People refineSearch API response into job dicts.

    Used by: Adobe and other Phenom-powered career sites.
    Endpoint: POST https://<domain>/widgets with ddoKey=refineSearch

    Args:
        api_response: Raw JSON response from the Phenom API.
        source_name: Name of the source for attribution.
        base_url: Base URL for building job links (e.g. "https://careers.adobe.com").

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []
    refine = api_response.get("refineSearch", {})
    hit_list = refine.get("data", {}).get("jobs", [])

    company = source_name.replace(" Careers", "").replace(" Jobs", "").strip()

    for job in hit_list:
        title = job.get("title", "Unknown Title")
        location = job.get("location", job.get("cityStateCountry", ""))
        job_id = job.get("jobId", job.get("reqId", ""))
        posted = job.get("postedDate", "")
        job_type = job.get("type", "Full time")
        teaser = job.get("descriptionTeaser", "")
        category = job.get("category", "")

        # Build job URL
        job_url = job.get("applyUrl", "")
        if not job_url and base_url and job_id:
            job_url = f"{base_url}/us/en/job/{job_id}"

        description = teaser
        if category:
            description = f"{category} | {teaser}" if teaser else category

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": job_url,
            "description": description,
            "date_posted": posted,
            "source": source_name,
            "job_type": job_type,
        })

    return jobs


def parse_goldmansachs_jobs_api(api_response: dict, source_name: str) -> list[dict]:
    """
    Parse a Goldman Sachs GraphQL API response into job dicts.

    Endpoint: POST https://api-higher.gs.com/gateway/api/v1/graphql
    Operation: GetRoles

    Args:
        api_response: Raw JSON response from the GS GraphQL API.
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []
    role_search = api_response.get("data", {}).get("roleSearch", {})
    items = role_search.get("items", [])

    for item in items:
        title = item.get("jobTitle", "Unknown Title")
        division = item.get("division", "")
        job_function = item.get("jobFunction", "")
        corporate_title = item.get("corporateTitle", "")

        # Build location from locations array
        locations = item.get("locations", [])
        location_parts = []
        for loc in locations:
            city = loc.get("city", "")
            state = loc.get("state", "")
            country = loc.get("country", "")
            parts = [p for p in [city, state, country] if p]
            if parts:
                location_parts.append(", ".join(parts))
        location = "; ".join(location_parts) if location_parts else "Not specified"

        # Build job URL from externalSource.sourceId
        source_id = item.get("externalSource", {}).get("sourceId", "")
        job_url = f"https://higher.gs.com/roles/{source_id}" if source_id else ""

        # Build description
        desc_parts = []
        if corporate_title:
            desc_parts.append(corporate_title)
        if division:
            desc_parts.append(division)
        if job_function:
            desc_parts.append(job_function)
        description = " | ".join(desc_parts)

        jobs.append({
            "title": title,
            "company": "Goldman Sachs",
            "location": location,
            "url": job_url,
            "description": description,
            "date_posted": "",
            "source": source_name,
            "job_type": "Full-time",
        })

    return jobs


def parse_epam_jobs_api(api_response: dict, source_name: str) -> list[dict]:
    """
    Parse an EPAM Anywhere /api/jobs/v2/search/careers-i18n API response into job dicts.

    Used by: EPAM Careers (careers.epam.com)
    The API returns nested JSON with data.jobs containing job objects.

    Args:
        api_response: Raw JSON response from the EPAM API.
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    data = api_response.get("data", {})
    raw_jobs = data.get("jobs", [])

    for raw_job in raw_jobs:
        title = raw_job.get("name", "Unknown")

        # Build location from city/state/country arrays
        cities = raw_job.get("city", [])
        countries = raw_job.get("country", [])
        location_parts = []
        if cities:
            city_info = cities[0]
            city_name = city_info.get("name", "")
            state_info = city_info.get("state", {})
            state_name = state_info.get("name", "") if state_info else ""
            if city_name:
                location_parts.append(city_name)
            if state_name:
                location_parts.append(state_name)
        if countries:
            country_name = countries[0].get("name", "")
            if country_name:
                location_parts.append(country_name)
        location = ", ".join(location_parts) if location_parts else "Not specified"

        # Build job URL from seo.url
        seo = raw_job.get("seo", {})
        relative_url = seo.get("url", "")
        job_url = f"https://careers.epam.com{relative_url}" if relative_url else ""

        # Description
        description = raw_job.get("description", "")
        # Strip HTML tags from description
        import re
        description = re.sub(r"<[^>]+>", "", description).strip()

        # Extract other metadata
        seniority = raw_job.get("seniority", "")
        primary_skill = raw_job.get("primary_skill", "")
        vacancy_type = raw_job.get("vacancy_type", "Full-time")

        company = source_name.replace(" Careers", "").replace(" Jobs", "")

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": job_url,
            "description": description[:500] if description else "",
            "date_posted": "",
            "source": source_name,
            "job_type": vacancy_type or "Full-time",
        })

    return jobs


def fetch_apple_jobs(keywords: str = "Software Engineer", page: int = 1) -> dict:
    """
    Fetch jobs from Apple's career API. Handles the CSRF token flow.

    Apple requires: visit page → GET /api/v1/CSRFToken → POST /api/v1/search
    """
    try:
        client = httpx.Client(
            timeout=15,
            follow_redirects=True,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        )

        # Step 1: Visit the page to establish session cookies
        client.get("https://jobs.apple.com/en-us/search")

        # Step 2: Get CSRF token
        csrf_resp = client.get("https://jobs.apple.com/api/v1/CSRFToken")
        csrf_token = csrf_resp.headers.get("x-apple-csrf-token", "")

        if not csrf_token:
            client.close()
            return {"success": False, "data": {}, "error": "Failed to get CSRF token"}

        # Step 3: Search
        body = {
            "query": keywords,
            "filters": {
                "locations": ["postLocation-USA"],
            },
            "page": page,
            "locale": "en-us",
            "sort": "relevance",
            "format": {
                "longDate": "MMMM D, YYYY",
                "mediumDate": "MMM D, YYYY",
            },
        }
        resp = client.post(
            "https://jobs.apple.com/api/v1/search",
            json=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-apple-csrf-token": csrf_token,
                "browserlocale": "en-us",
                "locale": "en_US",
            },
        )
        client.close()

        if resp.status_code == 200:
            return {"success": True, "data": resp.json(), "error": ""}
        else:
            return {"success": False, "data": {}, "error": f"API returned HTTP {resp.status_code}"}

    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


def parse_apple_jobs_api(api_response: dict, source_name: str) -> list[dict]:
    """
    Parse an Apple Jobs /api/v1/search API response into job dicts.

    Used by: Apple Careers (jobs.apple.com)
    The API returns nested JSON with res.searchResults containing job objects.

    Args:
        api_response: Raw JSON response from the Apple API.
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    res = api_response.get("res", api_response)
    raw_jobs = res.get("searchResults", [])

    for raw_job in raw_jobs:
        title = raw_job.get("postingTitle", "Unknown")

        # Build location from locations array
        locations = raw_job.get("locations", [])
        if locations:
            loc = locations[0]
            loc_name = loc.get("name", "")
            country = loc.get("countryName", "")
            location = f"{loc_name}, {country}" if loc_name and country else loc_name or country or "Not specified"
        else:
            location = "Not specified"

        # Build job URL
        job_id = raw_job.get("id", "")
        slug = raw_job.get("transformedPostingTitle", "")
        job_url = f"https://jobs.apple.com/en-us/details/{job_id}/{slug}" if job_id else ""

        # Description
        description = raw_job.get("jobSummary", "")

        # Parse posting date
        date_posted = raw_job.get("postingDate", "")

        # Team info
        team = raw_job.get("team", {})
        team_name = team.get("teamName", "") if team else ""

        jobs.append({
            "title": title,
            "company": "Apple",
            "location": location,
            "url": job_url,
            "description": description[:500] if description else "",
            "date_posted": date_posted,
            "source": source_name,
            "job_type": "Full-time",
        })

    return jobs


def fetch_servicenow_jobs(keywords: str = "Software Engineer", page: int = 1, page_size: int = 20) -> dict:
    """
    Fetch jobs from ServiceNow careers (SSR HTML parsing).

    ServiceNow uses server-side rendered HTML with no JSON API.
    Jobs are in .job-listing container with a[href] links.
    """
    import re
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {"success": False, "data": {"jobs": [], "total": 0}, "error": "beautifulsoup4 not installed"}

    try:
        url = "https://careers.servicenow.com/jobs/"
        params = {
            "search": keywords,
            "country": "United States",
            "pagesize": str(page_size),
            "page": str(page),
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        resp = httpx.get(url, params=params, headers=headers, timeout=15, follow_redirects=True, verify=False)

        if resp.status_code != 200:
            return {"success": False, "data": {"jobs": [], "total": 0}, "error": f"HTTP {resp.status_code}"}

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract total count from "Displaying 1 to 20 of 430 matching jobs"
        total = 0
        total_el = soup.select_one("[class*=total], [class*=count], [class*=result]")
        if total_el:
            text = total_el.get_text(strip=True)
            m = re.search(r"of\s*(\d+)", text)
            if m:
                total = int(m.group(1))

        # Extract jobs from .job-listing container
        jobs = []
        listing = soup.select_one(".job-listing")
        if listing:
            # Each job is an <a> with href like /jobs/{id}/{slug}/
            for link in listing.select("a[href]"):
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if not title or "/jobs/" not in href:
                    continue

                # Skip "Save" buttons
                if title.lower() in ("save", "saved"):
                    continue

                job_url = f"https://careers.servicenow.com{href}" if href.startswith("/") else href

                # Try to find location - in ul.job-meta inside the card-body grandparent
                location = "Not specified"
                parent = link.parent
                grandparent = parent.parent if parent else None
                if grandparent:
                    loc_meta = grandparent.select_one("ul.job-meta, [class*=job-meta]")
                    if loc_meta:
                        loc_text = loc_meta.get_text(strip=True)
                        if loc_text:
                            location = loc_text

                jobs.append({
                    "title": title,
                    "company": "ServiceNow",
                    "location": location,
                    "url": job_url,
                    "description": "",
                    "date_posted": "",
                    "source": "ServiceNow Careers",
                    "job_type": "Full-time",
                })

        return {"success": True, "data": {"jobs": jobs, "total": total}, "error": ""}

    except Exception as e:
        return {"success": False, "data": {"jobs": [], "total": 0}, "error": str(e)}
