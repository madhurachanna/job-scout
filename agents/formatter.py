"""
Formatter Agent — standardizes fields, saves results, and generates HTML report.
No LLM needed. Runs after all jobs have been collected and deduplicated.
"""

import os
from config.settings import settings
from tools.file_handler import save_to_json, save_to_csv, generate_summary
from tools.html_report import generate_html_report
from models.state import AgentState


# Standardized field order and defaults
STANDARD_FIELDS = {
    "title": "",
    "company": "",
    "location": "",
    "url": "",
    "description": "",
    "date_posted": "",
    "source": "",
    "job_type": "",
}


def _standardize_job(job: dict) -> dict:
    """
    Standardize a job dict to have all fields in a consistent order.
    Missing fields are set to empty strings (never None).
    """
    standardized = {}
    for field, default in STANDARD_FIELDS.items():
        value = job.get(field, default)
        # Replace None with empty string
        if value is None:
            value = ""
        # Strip whitespace from string values
        if isinstance(value, str):
            value = value.strip()
        standardized[field] = value
    return standardized


def formatter_agent(state: AgentState) -> dict:
    """
    Standardize all job fields, save to JSON/CSV, and generate an HTML report.
    This runs after deduplication — does not affect job search performance.
    """
    final_jobs = state.get("final_jobs", [])
    errors = state.get("errors", [])
    output_dir = settings.output_dir

    # Step 1: Standardize all job fields
    print(f"\n[Formatter] Standardizing {len(final_jobs)} jobs...")
    standardized_jobs = [_standardize_job(job) for job in final_jobs]

    # Step 2: Save to JSON
    print(f"[Formatter] Saving to {output_dir}/")
    json_path = save_to_json(standardized_jobs, output_dir)
    print(f"[Formatter]   📄 JSON: {json_path}")

    # Step 3: Save to CSV
    csv_path = save_to_csv(standardized_jobs, output_dir)
    print(f"[Formatter]   📄 CSV:  {csv_path}")

    # Step 4: Generate HTML report
    html_path = os.path.join(output_dir, "jobs.html")
    generate_html_report(standardized_jobs, html_path)
    print(f"[Formatter]   🌐 HTML: {html_path}")

    # Step 5: Print summary
    summary = generate_summary(standardized_jobs)
    print(f"\n{summary}")

    # Print any errors that occurred
    if errors:
        print(f"\n⚠️  Errors encountered during scraping:")
        for error in errors:
            print(f"  - {error}")

    return {
        "final_jobs": standardized_jobs,
        "errors": [],
    }
