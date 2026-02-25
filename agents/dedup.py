"""
Dedup Agent — deterministic deduplication, date filtering, and filtering of job listings.
No LLM needed.
"""

from datetime import datetime, timedelta, timezone
from models.state import AgentState


# Only show jobs posted within this many days
MAX_AGE_DAYS = 2

# US state abbreviations (2-letter codes used in "City, ST" location strings)
_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",  # Washington D.C.
}

# Keywords that unambiguously indicate a non-US location
_NON_US_KEYWORDS = {
    "united kingdom", "uk", "england", "scotland", "wales",
    "canada", "ontario", "british columbia", "quebec", "alberta",
    "india", "bangalore", "hyderabad", "mumbai", "delhi", "pune", "chennai",
    "australia", "sydney", "melbourne",
    "germany", "berlin", "munich",
    "france", "paris",
    "netherlands", "amsterdam",
    "ireland", "dublin",
    "singapore",
    "japan", "tokyo",
    "china", "beijing", "shanghai",
    "brazil", "são paulo",
    "mexico",
    "poland", "warsaw",
    "sweden", "stockholm",
    "switzerland", "zurich",
    "spain", "madrid",
    "italy", "milan", "rome",
    "israel", "tel aviv",
}


def _is_us_location(location: str) -> bool:
    """
    Return True if the location is in the United States (or is ambiguous/remote).

    Strategy:
    - Blank / "Not specified" / "Remote" → keep (no filtering)
    - "City, XX" where XX is a US state code → keep
    - Known non-US keywords → drop
    - Anything else → keep (avoid false positives)
    """
    if not location:
        return True

    loc_lower = location.lower().strip()

    # Keep remote / unspecified jobs
    if loc_lower in ("", "not specified", "remote", "united states", "us", "usa"):
        return True
    if "remote" in loc_lower and ("us" in loc_lower or "united states" in loc_lower):
        return True
    if loc_lower == "remote":
        return True

    # Check for "City, ST" pattern — if ST matches a US state, it's US
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        last_part = parts[-1].strip().upper()
        if last_part in _US_STATES:
            return True

    # Check for explicit "United States" mention
    if "united states" in loc_lower or ", usa" in loc_lower or ", us" in loc_lower:
        return True

    # Check for known non-US keywords
    for keyword in _NON_US_KEYWORDS:
        if keyword in loc_lower:
            return False

    # Unknown / ambiguous → keep (avoid false positives)
    return True


def dedup_agent(state: AgentState) -> dict:
    """
    Deduplicate, date-filter, and clean the accumulated normalized jobs.

    - Removes duplicates based on (title, company, location)
    - Filters out jobs older than MAX_AGE_DAYS
    - Filters out non-US locations
    - Filters out entries with missing required fields
    """
    normalized_jobs = state.get("normalized_jobs", [])

    if not normalized_jobs:
        print("[Dedup] No jobs to deduplicate")
        return {
            "final_jobs": [],
            "errors": [],
        }

    print(f"[Dedup] Processing {len(normalized_jobs)} total jobs...")

    # Date cutoff: only keep jobs from last N days
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    print(f"[Dedup] Date filter: only jobs posted after {cutoff.strftime('%Y-%m-%d %H:%M UTC')}")

    seen_keys = set()
    unique_jobs = []
    filtered_by_date = 0
    filtered_by_location = 0

    for job in normalized_jobs:
        # Skip jobs without a title
        title = job.get("title", "").strip()
        if not title:
            continue

        # Date filter
        date_posted = job.get("date_posted", "")
        if date_posted:
            try:
                # Parse ISO format: 2026-02-14T13:46:00+0000
                if date_posted.endswith("+0000"):
                    dt = datetime.strptime(date_posted, "%Y-%m-%dT%H:%M:%S%z")
                else:
                    dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))

                if dt < cutoff:
                    filtered_by_date += 1
                    continue
            except (ValueError, TypeError):
                pass  # If date can't be parsed, keep the job

        # US-only location filter
        raw_location = job.get("location", "")
        if not _is_us_location(raw_location):
            filtered_by_location += 1
            continue

        # Build dedup key
        company = job.get("company", "").lower().strip()
        location = raw_location.lower().strip()
        dedup_key = f"{title.lower()}|{company}|{location}"

        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            unique_jobs.append(job)

    duplicates_removed = len(normalized_jobs) - len(unique_jobs) - filtered_by_date - filtered_by_location
    print(f"[Dedup] Filtered out {filtered_by_date} jobs older than {MAX_AGE_DAYS} days")
    print(f"[Dedup] Filtered out {filtered_by_location} non-US jobs")
    print(f"[Dedup] Removed {duplicates_removed} duplicates")
    print(f"[Dedup] {len(unique_jobs)} recent US-based unique jobs remaining")

    return {
        "final_jobs": unique_jobs,
        "errors": [],
    }
