"""
File Handler Tool — loads configs, saves results to JSON and CSV.
"""

import csv
import json
import os
from datetime import datetime

import yaml


def load_career_pages(yaml_path: str) -> list[dict]:
    """
    Load career page configurations from a YAML file.

    Args:
        yaml_path: Path to the career_pages.yaml file.

    Returns:
        List of career page dicts with keys: name, url, type.
    """
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    pages = data.get("career_pages", [])

    # Validate required fields
    validated = []
    for page in pages:
        if "url" in page and "name" in page:
            entry = {
                "name": page["name"],
                "url": page["url"],
                "type": page.get("type", "career_page"),
            }
            # Pass through optional fields
            if "api_url" in page:
                entry["api_url"] = page["api_url"]
            if "keywords" in page:
                entry["keywords"] = page["keywords"]
            validated.append(entry)

    return validated


def save_to_json(jobs: list[dict], output_dir: str, filename: str = None) -> str:
    """
    Save job listings to a JSON file.

    Args:
        jobs: List of job dicts to save.
        output_dir: Directory to save the file in.
        filename: Optional filename (auto-generated with timestamp if not provided).

    Returns:
        Path to the saved file.
    """
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.json"

    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w") as f:
        json.dump(jobs, f, indent=2, default=str)

    return filepath


def save_to_csv(jobs: list[dict], output_dir: str, filename: str = None) -> str:
    """
    Save job listings to a CSV file.

    Args:
        jobs: List of job dicts to save.
        output_dir: Directory to save the file in.
        filename: Optional filename (auto-generated with timestamp if not provided).

    Returns:
        Path to the saved file.
    """
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"jobs_{timestamp}.csv"

    filepath = os.path.join(output_dir, filename)

    if not jobs:
        # Write empty file with headers
        fieldnames = ["title", "company", "location", "url", "description", "date_posted", "source", "job_type"]
    else:
        fieldnames = list(jobs[0].keys())

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)

    return filepath


def generate_summary(jobs: list[dict]) -> str:
    """
    Generate a human-readable summary of the scraped jobs.

    Args:
        jobs: List of job dicts.

    Returns:
        Formatted summary string.
    """
    if not jobs:
        return "No jobs found."

    # Count by company
    companies = {}
    for job in jobs:
        company = job.get("company", "Unknown")
        companies[company] = companies.get(company, 0) + 1

    # Count by location
    locations = {}
    for job in jobs:
        location = job.get("location", "Unknown")
        locations[location] = locations.get(location, 0) + 1

    lines = [
        f"{'=' * 50}",
        f"  JOB SCRAPING SUMMARY",
        f"{'=' * 50}",
        f"  Total jobs found: {len(jobs)}",
        f"",
        f"  By Company:",
    ]
    for company, count in sorted(companies.items(), key=lambda x: -x[1]):
        lines.append(f"    - {company}: {count}")

    lines.append(f"")
    lines.append(f"  By Location:")
    for location, count in sorted(locations.items(), key=lambda x: -x[1]):
        lines.append(f"    - {location}: {count}")

    lines.append(f"{'=' * 50}")

    return "\n".join(lines)
