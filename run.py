"""
Job Scout — Multi-Agent Job Scraper
CLI entry point for running the job scraping workflow.
"""

import argparse
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from tools.file_handler import load_career_pages
from tools.job_store import init_db, mark_seen, get_seen_count
from tools.notifier import send_email_notification
from graph.workflow import graph
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


def _scrape_one_company(page: dict) -> tuple[list[dict], list[str], str]:
    """
    Run the full scrape→parse→normalize pipeline for a single company.
    Returns (normalized_jobs, errors, error_msg).
    """
    from agents.scraper import scraper_agent
    from agents.parser import parser_agent
    from agents.normalizer import normalizer_agent

    name = page.get("name", "Unknown")

    # Minimal state for this single company
    state: dict = {
        "career_pages": [page],
        "scraping_plan": [page],
        "current_page_index": 0,
        "current_page": page,
        "raw_html": "",
        "cleaned_text": "",
        "extracted_jobs": [],
        "normalized_jobs": [],
        "final_jobs": [],
        "errors": [],
    }

    try:
        state.update(scraper_agent(state))
        state.update(parser_agent(state))
        state.update(normalizer_agent(state))
        errs = state.get("errors", [])
        # Surface the first error message for display if any
        err_msg = errs[0].split(": ", 1)[-1] if errs else ""
        return state.get("normalized_jobs", []), errs, err_msg
    except Exception as e:
        print(f"[Parallel] ❌ {name} failed: {e}")
        return [], [f"{name}: {e}"], str(e)


def run_once(career_pages: list[dict], db_path: str = None) -> tuple[list[dict], list[str], dict, set]:
    """
    Run one scraping cycle.
    Phase 1: API scrapers in parallel (batched, max 5 workers).
    Phase 2: Browser scrapers serially (one at a time — RAM-safe for EC2).
    Phase 3: HTML/LLM scrapers (max 3 workers).
    Returns (final_jobs, errors, scrape_results, new_keys).
    """
    from agents.planner import planner_agent
    from agents.dedup import dedup_agent
    from agents.formatter import formatter_agent

    # Run planner to get ordered/filtered scraping plan
    plan_state: dict = {
        "career_pages": career_pages,
        "scraping_plan": [],
        "current_page_index": 0,
        "current_page": {},
        "raw_html": "",
        "cleaned_text": "",
        "extracted_jobs": [],
        "normalized_jobs": [],
        "final_jobs": [],
        "errors": [],
    }
    plan_state.update(planner_agent(plan_state))
    scraping_plan = plan_state.get("scraping_plan", [])

    if not scraping_plan:
        print("⚠️  No pages to scrape.")
        return [], [], {}

    # Split by type
    api_pages     = [p for p in scraping_plan if p.get("type") == "api"]
    browser_pages = [p for p in scraping_plan if p.get("type") == "browser"]
    html_pages    = [p for p in scraping_plan if p.get("type") not in ("api", "browser")]
    total = len(scraping_plan)

    all_normalized: list[dict] = []
    all_errors: list[str] = []
    statuses: dict[str, dict] = {}
    error_count = 0

    # Initialize statuses
    for p in scraping_plan:
        n = p.get("name", "?")
        t = p.get("type", "html")
        statuses[n] = {"type": t, "state": "waiting", "jobs": 0, "error": ""}

    TYPE_LABELS = {"api": "API", "browser": "BROWSER", "html": "HTML"}
    TYPE_ICONS  = {"api": "🔌", "browser": "🌐", "html": "📄"}

    def _fmt_line(name, ptype, status_str):
        icon = TYPE_ICONS.get(ptype, "📄")
        label = TYPE_LABELS.get(ptype, "HTML")
        padded_name = name.ljust(28)
        dots = "·" * max(2, 30 - len(name))
        return f"  {icon} [{label:7s}] {padded_name} {dots} {status_str}"

    def _scrape_and_log(page):
        nonlocal error_count
        name = page.get("name", "?")
        ptype = page.get("type", "html")
        statuses[name]["state"] = "scraping"

        jobs, errs, err_msg = _scrape_one_company(page)

        if errs and not jobs:
            statuses[name]["state"] = "error"
            statuses[name]["error"] = err_msg
            error_count += 1
            short_err = err_msg[:60] if err_msg else "Unknown error"
            print(_fmt_line(name, ptype, f"❌ {short_err}"))
        else:
            statuses[name]["state"] = "done"
            statuses[name]["jobs"] = len(jobs)
            print(_fmt_line(name, ptype, f"✅ {len(jobs)} jobs"))

        return jobs, errs

    # ── Header ────────────────────────────────────────────────────
    print(f"\n🚀 Scraping {total} companies "
          f"({len(api_pages)} API · {len(browser_pages)} Browser · {len(html_pages)} HTML)\n")

    # ── Phase 1: API scrapers in parallel (batched, max 5 workers) ──
    if api_pages:
        print(f"── Phase 1: API scrapers ({len(api_pages)} companies, parallel) ──")
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_scrape_and_log, p): p for p in api_pages}
            for future in as_completed(futures):
                try:
                    jobs, errs = future.result()
                    all_normalized.extend(jobs)
                    all_errors.extend(errs)
                except Exception as e:
                    name = futures[future].get("name", "?")
                    statuses[name]["state"] = "error"
                    statuses[name]["error"] = str(e)
                    error_count += 1
                    all_errors.append(f"{name}: {e}")
                    print(_fmt_line(name, "api", f"❌ {str(e)[:60]}"))

    # ── Phase 2: Browser scrapers SERIALLY (one at a time for RAM) ──
    if browser_pages:
        print(f"\n── Phase 2: Browser scrapers ({len(browser_pages)} companies, serial) ──")
        for page in browser_pages:
            try:
                jobs, errs = _scrape_and_log(page)
                all_normalized.extend(jobs)
                all_errors.extend(errs)
            except Exception as e:
                name = page.get("name", "?")
                statuses[name]["state"] = "error"
                statuses[name]["error"] = str(e)
                error_count += 1
                all_errors.append(f"{name}: {e}")
                print(_fmt_line(name, "browser", f"❌ {str(e)[:60]}"))

    # ── Phase 3: HTML/LLM scrapers (max 3 workers) ──────────────
    if html_pages:
        print(f"\n── Phase 3: HTML scrapers ({len(html_pages)} companies) ──")
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_scrape_and_log, p): p for p in html_pages}
            for future in as_completed(futures):
                try:
                    jobs, errs = future.result()
                    all_normalized.extend(jobs)
                    all_errors.extend(errs)
                except Exception as e:
                    name = futures[future].get("name", "?")
                    statuses[name]["state"] = "error"
                    statuses[name]["error"] = str(e)
                    error_count += 1
                    all_errors.append(f"{name}: {e}")

    # ── Dedup + format ────────────────────────────────────────────
    print(f"\n📦 Aggregated {len(all_normalized)} jobs — deduplicating...")

    final_state: dict = {
        **plan_state,
        "normalized_jobs": all_normalized,
        "errors": all_errors,
    }
    final_state.update(dedup_agent(final_state))

    # Mark jobs as seen in the DB and get which ones are new
    new_keys: set = set()
    deduped_jobs = final_state.get("final_jobs", [])
    if db_path and deduped_jobs:
        new_keys = mark_seen(deduped_jobs, db_path)
        print(f"\n🆕 {len(new_keys)} new jobs (not previously seen)")

    # Pass new_keys and scrape_results to formatter for the HTML report
    final_state["new_keys"] = new_keys
    final_state["scrape_results"] = statuses

    final_state.update(formatter_agent(final_state))

    return final_state.get("final_jobs", []), final_state.get("errors", []), statuses, new_keys



def main():
    """Main entry point for the job scraping system."""
    parser = argparse.ArgumentParser(
        description="Job Scout — Multi-Agent Job Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py
  python run.py --config config/career_pages.yaml
  python run.py --output-dir results/
  python run.py --schedule 60 --notify-email you@example.com
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/career_pages.yaml",
        help="Path to career pages YAML config (default: config/career_pages.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Output directory for results (default: {settings.output_dir})",
    )
    parser.add_argument(
        "--skip-normalization",
        action="store_true",
        help="Skip LLM-based normalization (faster, but less consistent data)",
    )
    parser.add_argument(
        "--schedule",
        type=int,
        default=None,
        metavar="MINUTES",
        help="Run on a schedule every N minutes (e.g. --schedule 60). Emails new jobs only.",
    )
    parser.add_argument(
        "--notify-email",
        type=str,
        default=None,
        help="Email address to send new job notifications to (requires SMTP config in .env)",
    )

    args = parser.parse_args()

    # Update settings
    if args.output_dir:
        settings.output_dir = args.output_dir
    if args.skip_normalization:
        settings.skip_normalization = True

    # Load career pages
    config_path = args.config
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)

    career_pages = load_career_pages(config_path)
    if not career_pages:
        print("❌ No career pages found in config file.")
        sys.exit(1)

    # Resolve notify email (CLI arg > .env setting)
    notify_email = args.notify_email or settings.notify_email

    # Validate email config if scheduling
    if args.schedule and notify_email:
        if not settings.smtp_user or not settings.smtp_password:
            print("❌ SMTP_USER and SMTP_PASSWORD must be set in .env for email notifications.")
            print("   See .env.example for configuration details.")
            sys.exit(1)

    print("=" * 60)
    print("  🔍 Job Scout — Multi-Agent Job Scraper")
    print("=" * 60)
    print(f"  LLM:    {settings.llm_model_name} @ {settings.llm_base_url}")
    print(f"  Pages:  {len(career_pages)} career pages to scrape")
    print(f"  Output: {settings.output_dir}/")
    if args.schedule:
        print(f"  Mode:   ⏰ Scheduled every {args.schedule} min")
        if notify_email:
            print(f"  Email:  📧 {notify_email}")
    print("=" * 60)
    print()

    # Check LLM connectivity before starting
    has_html_pages = any(p.get("type") != "api" for p in career_pages)
    print("🔌 Checking LLM connectivity...", end=" ")
    try:
        import httpx
        resp = httpx.get(
            f"{settings.llm_base_url}/models",
            timeout=10,
            headers={"Authorization": "Bearer lm-studio"},
        )
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            model_names = [m.get("id", "unknown") for m in models]
            print(f"✅ Connected! Available models: {', '.join(model_names)}")
        else:
            print(f"⚠️  Server responded with HTTP {resp.status_code}")
    except Exception as e:
        if has_html_pages:
            print(f"❌ Cannot reach LM Studio at {settings.llm_base_url}")
            print(f"   Error: {e}")
            print(f"\n   Please check:")
            print(f"   1. LM Studio is running on the Windows machine")
            print(f"   2. 'Serve on Local Network' is enabled in LM Studio")
            print(f"   3. The IP in .env is correct (currently: {settings.llm_base_url})")
            print(f"   4. No firewall is blocking port 1234")
            sys.exit(1)
        else:
            print(f"⚠️  LLM not reachable, but all pages are API-mode — continuing without LLM")
    print()

    # ── Scheduled mode ───────────────────────────────────────
    if args.schedule:
        interval = args.schedule

        # Initialize job store
        init_db(settings.db_path)
        seen = get_seen_count(settings.db_path)
        print(f"📦 Job store initialized: {seen} previously seen jobs")
        print(f"⏰ Starting scheduler — running every {interval} minutes")
        print(f"   Press Ctrl+C to stop.\n")

        cycle = 0
        while True:
            cycle += 1
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            print(f"\n{'─' * 60}")
            print(f"  Cycle #{cycle} — {now}")
            print(f"{'─' * 60}\n")

            try:
                final_jobs, errors, _statuses, new_keys = run_once(career_pages, db_path=settings.db_path)

                if final_jobs:
                    # new_keys already populated by run_once via mark_seen
                    from tools.job_store import _make_dedup_key
                    new_jobs = [j for j in final_jobs if _make_dedup_key(j) in new_keys]

                    print(f"\n📊 Results: {len(final_jobs)} total, {len(new_jobs)} new")

                    if new_jobs and notify_email:
                        send_email_notification(
                            new_jobs,
                            recipient=notify_email,
                            smtp_host=settings.smtp_host,
                            smtp_port=settings.smtp_port,
                            smtp_user=settings.smtp_user,
                            smtp_password=settings.smtp_password,
                        )
                    elif new_jobs:
                        print(f"📋 New jobs (no email configured):")
                        for job in new_jobs[:10]:
                            print(f"   • {job.get('title')} at {job.get('company')} — {job.get('location')}")
                        if len(new_jobs) > 10:
                            print(f"   ... and {len(new_jobs) - 10} more")
                    else:
                        print(f"✅ No new jobs since last run.")
                else:
                    print(f"⚠️  No jobs found this cycle.")

                if errors:
                    print(f"⚠️  {len(errors)} error(s):")
                    for e in errors:
                        print(f"   - {e}")

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"❌ Cycle #{cycle} failed: {e}")

            print(f"\n💤 Sleeping {interval} minutes until next run...")
            try:
                time.sleep(interval * 60)
            except KeyboardInterrupt:
                print("\n\n⛔ Scheduler stopped.")
                sys.exit(0)

    # ── Single run mode ──────────────────────────────────────
    else:
        try:
            final_jobs, errors, _statuses, _new_keys = run_once(career_pages, db_path=settings.db_path)

            print(f"\n✅ Done! Found {len(final_jobs)} unique jobs.")
            if errors:
                print(f"⚠️  {len(errors)} errors occurred during scraping.")

            # If email flag is set, send a one-time notification
            if notify_email and final_jobs:
                if settings.smtp_user and settings.smtp_password:
                    send_email_notification(
                        final_jobs,
                        recipient=notify_email,
                        smtp_host=settings.smtp_host,
                        smtp_port=settings.smtp_port,
                        smtp_user=settings.smtp_user,
                        smtp_password=settings.smtp_password,
                    )
                else:
                    print("⚠️  Email requested but SMTP not configured in .env")

        except KeyboardInterrupt:
            print("\n\n⛔ Scraping interrupted by user.")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            raise


if __name__ == "__main__":
    main()
