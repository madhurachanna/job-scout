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
) -> dict:
    """
    Fetch jobs from a JSON API endpoint.

    Args:
        api_url: The API endpoint URL.
        params: Query parameters for the API call.
        timeout: Request timeout in seconds.

    Returns:
        dict with keys:
            - success (bool)
            - data (dict): Raw API response
            - error (str): Error message if failed
    """
    timeout = timeout or settings.request_timeout

    try:
        with httpx.Client(
            timeout=timeout,
            verify=False,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",  # Exclude brotli to avoid decompressobj reuse bug
            },
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
) -> dict:
    """
    Fetch jobs from a JSON API endpoint using POST.
    Used for Workday-style APIs that require POST with JSON body.
    """
    timeout = timeout or settings.request_timeout

    try:
        with httpx.Client(
            timeout=timeout,
            verify=False,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
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


def parse_microsoft_jobs_api(api_response: dict, source_name: str) -> list[dict]:
    """
    Parse the Microsoft Careers pcsx/search API response into job dicts.

    Args:
        api_response: Raw JSON response from the Microsoft search API.
        source_name: Name of the source for attribution.

    Returns:
        List of job dicts ready for the normalizer.
    """
    jobs = []

    data = api_response.get("data", {})
    raw_jobs = data.get("positions", [])

    for raw_job in raw_jobs:
        # Build location from locations array
        locations = raw_job.get("locations", [])
        location = ", ".join(locations) if locations else "Not specified"

        # Build job URL
        position_url = raw_job.get("positionUrl", "")
        job_url = f"https://apply.careers.microsoft.com{position_url}" if position_url else ""

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
        description = f"Microsoft Job ID: {display_id}" if display_id else ""

        jobs.append({
            "title": raw_job.get("name", "Unknown"),
            "company": "Microsoft",
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

        jobs.append({
            "title": raw_job.get("title", "Unknown"),
            "company": "GEICO",
            "location": location,
            "url": job_url,
            "description": raw_job.get("bulletFields", [""])[0] if raw_job.get("bulletFields") else "",
            "date_posted": date_posted,
            "source": source_name,
            "job_type": "Full-time",
        })

    return jobs
