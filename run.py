"""
Job Scout — Multi-Agent Job Scraper
CLI entry point for running the job scraping workflow.
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from tools.file_handler import load_career_pages
from graph.workflow import graph


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

    print("=" * 60)
    print("  🔍 Job Scout — Multi-Agent Job Scraper")
    print("=" * 60)
    print(f"  LLM:    {settings.llm_model_name} @ {settings.llm_base_url}")
    print(f"  Pages:  {len(career_pages)} career pages to scrape")
    print(f"  Output: {settings.output_dir}/")
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

    # Build initial state
    initial_state = {
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

    # Run the workflow
    try:
        result = graph.invoke(initial_state)

        # Final status
        final_jobs = result.get("final_jobs", [])
        errors = result.get("errors", [])

        print(f"\n✅ Done! Found {len(final_jobs)} unique jobs.")
        if errors:
            print(f"⚠️  {len(errors)} errors occurred during scraping.")

    except KeyboardInterrupt:
        print("\n\n⛔ Scraping interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
