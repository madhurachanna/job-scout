"""
Tests for tools/job_store.py — focusing on the session-based "new jobs" detection.
"""
import os
import tempfile
import pytest
from tools.job_store import init_db, mark_seen, get_new_jobs, get_seen_count, _make_dedup_key


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a fresh temp SQLite database path for each test."""
    db_path = str(tmp_path / "test_jobs.db")
    init_db(db_path)
    return db_path


def _job(title="SWE", company="Acme", location="New York, NY"):
    return {"title": title, "company": company, "location": location, "url": "https://example.com"}


# ── mark_seen return value ──────────────────────────────────────────────────

def test_mark_seen_returns_new_keys_on_first_run(tmp_db):
    """All jobs should be 'new' on the very first scrape."""
    jobs = [_job("Engineer"), _job("Analyst"), _job("Manager")]
    new_keys = mark_seen(jobs, tmp_db)
    assert len(new_keys) == 3
    for job in jobs:
        assert _make_dedup_key(job) in new_keys


def test_mark_seen_returns_empty_on_second_run_with_same_jobs(tmp_db):
    """Calling mark_seen twice with the same jobs: no new keys on the 2nd call."""
    jobs = [_job("Engineer"), _job("Analyst")]
    first_new = mark_seen(jobs, tmp_db)
    assert len(first_new) == 2

    second_new = mark_seen(jobs, tmp_db)
    assert len(second_new) == 0, "Jobs already in DB should NOT appear as new again"


def test_mark_seen_only_returns_truly_new_jobs(tmp_db):
    """Second scrape adds one new job — only that one should be in new_keys."""
    old_jobs = [_job("Engineer"), _job("Analyst")]
    mark_seen(old_jobs, tmp_db)  # First run: these are now "seen"

    # Second run has 3 jobs: 2 old + 1 brand new
    new_job = _job("Director")
    all_jobs = old_jobs + [new_job]
    new_keys = mark_seen(all_jobs, tmp_db)

    assert len(new_keys) == 1
    assert _make_dedup_key(new_job) in new_keys


def test_mark_seen_empty_list_returns_empty_set(tmp_db):
    new_keys = mark_seen([], tmp_db)
    assert new_keys == set()


# ── get_new_jobs (legacy / scheduled mode) ─────────────────────────────────

def test_get_new_jobs_matches_mark_seen_for_fresh_db(tmp_db):
    """get_new_jobs should agree with mark_seen when no jobs are pre-seen."""
    jobs = [_job("A"), _job("B")]
    pre_scan = get_new_jobs(jobs, tmp_db)
    assert len(pre_scan) == 2  # Both are new

    new_keys = mark_seen(jobs, tmp_db)
    assert len(new_keys) == 2


def test_get_new_jobs_returns_empty_after_mark_seen(tmp_db):
    jobs = [_job("A"), _job("B")]
    mark_seen(jobs, tmp_db)
    leftover = get_new_jobs(jobs, tmp_db)
    assert leftover == []


# ── Dedup key robustness ────────────────────────────────────────────────────

def test_dedup_key_is_case_insensitive(tmp_db):
    """Jobs with same title/company/location in different cases should dedup."""
    job1 = _job("Software Engineer", "Google", "Mountain View, CA")
    job2 = _job("software engineer", "google", "mountain view, ca")
    
    new_keys = mark_seen([job1, job2], tmp_db)
    # key1 and key2 are identical after lowercasing → only 1 inserted
    assert len(new_keys) == 1


def test_different_locations_create_different_keys(tmp_db):
    """Same title+company but different locations = 2 distinct jobs."""
    job_nyc = _job("SWE", "Stripe", "New York, NY")
    job_sf = _job("SWE", "Stripe", "San Francisco, CA")
    
    new_keys = mark_seen([job_nyc, job_sf], tmp_db)
    assert len(new_keys) == 2


# ── get_seen_count ──────────────────────────────────────────────────────────

def test_get_seen_count_tracks_insertions(tmp_db):
    assert get_seen_count(tmp_db) == 0
    mark_seen([_job("A"), _job("B")], tmp_db)
    assert get_seen_count(tmp_db) == 2
    mark_seen([_job("A"), _job("C")], tmp_db)  # A is a dupe, C is new
    assert get_seen_count(tmp_db) == 3  # A + B + C
