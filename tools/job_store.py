"""
Job Store — SQLite-based persistence for tracking seen jobs.
Used by the scheduler to only surface new postings.
"""

import os
import sqlite3
from datetime import datetime, timezone


DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "job_scout.db",
)


def _get_connection(db_path: str = None) -> sqlite3.Connection:
    """Get a SQLite connection, creating the database and directory if needed."""
    db_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return sqlite3.connect(db_path)


def init_db(db_path: str = None) -> None:
    """Create the seen_jobs table if it doesn't exist."""
    conn = _get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dedup_key TEXT UNIQUE NOT NULL,
                title TEXT,
                company TEXT,
                url TEXT,
                first_seen_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_dedup_key ON seen_jobs(dedup_key)
        """)
        conn.commit()
    finally:
        conn.close()


def _make_dedup_key(job: dict) -> str:
    """Build a unique key for a job (same logic as dedup agent)."""
    title = job.get("title", "").lower().strip()
    company = job.get("company", "").lower().strip()
    location = job.get("location", "").lower().strip()
    return f"{title}|{company}|{location}"


def get_new_jobs(jobs: list[dict], db_path: str = None) -> list[dict]:
    """
    Filter jobs, returning only those not previously seen.

    Args:
        jobs: List of job dicts to check.
        db_path: Path to SQLite database.

    Returns:
        List of job dicts that are new (not in the DB).
    """
    if not jobs:
        return []

    conn = _get_connection(db_path)
    try:
        cursor = conn.cursor()
        new_jobs = []
        for job in jobs:
            key = _make_dedup_key(job)
            cursor.execute("SELECT 1 FROM seen_jobs WHERE dedup_key = ?", (key,))
            if cursor.fetchone() is None:
                new_jobs.append(job)
        return new_jobs
    finally:
        conn.close()


def mark_seen(jobs: list[dict], db_path: str = None) -> int:
    """
    Insert jobs into the seen_jobs table.

    Args:
        jobs: List of job dicts to mark as seen.
        db_path: Path to SQLite database.

    Returns:
        Number of newly inserted jobs.
    """
    if not jobs:
        return 0

    conn = _get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    try:
        for job in jobs:
            key = _make_dedup_key(job)
            try:
                conn.execute(
                    "INSERT INTO seen_jobs (dedup_key, title, company, url, first_seen_at) VALUES (?, ?, ?, ?, ?)",
                    (key, job.get("title", ""), job.get("company", ""), job.get("url", ""), now),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass  # Already exists

        conn.commit()
        return inserted
    finally:
        conn.close()


def get_seen_count(db_path: str = None) -> int:
    """Return total number of seen jobs in the database."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM seen_jobs")
        return cursor.fetchone()[0]
    finally:
        conn.close()
