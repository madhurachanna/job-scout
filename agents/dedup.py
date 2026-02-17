"""
Dedup Agent — deterministic deduplication, date filtering, and filtering of job listings.
No LLM needed.
"""

from datetime import datetime, timedelta, timezone
from models.state import AgentState


# Only show jobs posted within this many days
MAX_AGE_DAYS = 2


def dedup_agent(state: AgentState) -> dict:
    """
    Deduplicate, date-filter, and clean the accumulated normalized jobs.

    - Removes duplicates based on (title, company, location)
    - Filters out jobs older than MAX_AGE_DAYS
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

        # Build dedup key
        company = job.get("company", "").lower().strip()
        location = job.get("location", "").lower().strip()
        dedup_key = f"{title.lower()}|{company}|{location}"

        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            unique_jobs.append(job)

    duplicates_removed = len(normalized_jobs) - len(unique_jobs) - filtered_by_date
    print(f"[Dedup] Filtered out {filtered_by_date} jobs older than {MAX_AGE_DAYS} days")
    print(f"[Dedup] Removed {duplicates_removed} duplicates")
    print(f"[Dedup] {len(unique_jobs)} recent unique jobs remaining")

    return {
        "final_jobs": unique_jobs,
        "errors": [],
    }
