"""
HTML Report Generator — creates a beautiful static HTML page for job listings.
"""

from datetime import datetime


def generate_html_report(jobs: list[dict], output_path: str) -> str:
    """
    Generate a static HTML page displaying all job listings.

    Args:
        jobs: List of standardized job dicts.
        output_path: Path to save the HTML file.

    Returns:
        Path to the generated HTML file.
    """
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    # Group jobs by company
    companies = {}
    for job in jobs:
        company = job.get("company", "Unknown")
        if company not in companies:
            companies[company] = []
        companies[company].append(job)

    # Build job cards HTML
    job_cards_html = ""
    for company, company_jobs in sorted(companies.items()):
        job_cards_html += f'<div class="company-section">\n'
        job_cards_html += f'  <h2 class="company-name">{_esc(company)} <span class="badge">{len(company_jobs)}</span></h2>\n'
        job_cards_html += f'  <div class="job-grid">\n'

        for job in company_jobs:
            title = _esc(job.get("title", ""))
            location = _esc(job.get("location", ""))
            job_type = _esc(job.get("job_type", ""))
            url = job.get("url", "")
            description = _esc(job.get("description", ""))
            date_posted = job.get("date_posted", "")
            source = _esc(job.get("source", ""))

            # Format date
            date_display = ""
            if date_posted:
                try:
                    if date_posted.endswith("+0000"):
                        dt = datetime.strptime(date_posted, "%Y-%m-%dT%H:%M:%S%z")
                    else:
                        dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
                    date_display = dt.strftime("%b %d, %Y")
                except (ValueError, TypeError):
                    date_display = date_posted

            # Truncate description for card
            desc_short = description[:200] + "..." if len(description) > 200 else description

            job_cards_html += f"""    <div class="job-card">
      <div class="job-header">
        <h3 class="job-title">{title}</h3>
        {f'<span class="job-type">{job_type}</span>' if job_type else ''}
      </div>
      <div class="job-meta">
        {f'<span class="meta-item">📍 {location}</span>' if location else ''}
        {f'<span class="meta-item">📅 {date_display}</span>' if date_display else ''}
        {f'<span class="meta-item">📂 {source}</span>' if source else ''}
      </div>
      {f'<p class="job-description">{desc_short}</p>' if desc_short else ''}
      {f'<a href="{url}" target="_blank" class="apply-btn">View Job →</a>' if url else ''}
    </div>
"""
        job_cards_html += '  </div>\n</div>\n'

    # Summary stats
    total = len(jobs)
    companies_count = len(companies)
    locations = {}
    for job in jobs:
        loc = job.get("location", "Unknown")
        locations[loc] = locations.get(loc, 0) + 1
    remote_count = sum(v for k, v in locations.items() if "remote" in k.lower())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Listings — {timestamp}</title>
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background: #0f0f23;
      color: #e0e0e0;
      min-height: 100vh;
    }}

    .header {{
      background: linear-gradient(135deg, #1a1a3e 0%, #0d0d2b 100%);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding: 2rem 2rem 1.5rem;
    }}

    .header h1 {{
      font-size: 1.8rem;
      font-weight: 700;
      color: #fff;
      margin-bottom: 0.5rem;
    }}

    .header h1 span {{
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .header .subtitle {{
      color: #888;
      font-size: 0.9rem;
    }}

    .stats {{
      display: flex;
      gap: 1.5rem;
      margin-top: 1.2rem;
      flex-wrap: wrap;
    }}

    .stat {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      padding: 0.8rem 1.2rem;
      min-width: 120px;
    }}

    .stat-value {{
      font-size: 1.6rem;
      font-weight: 700;
      color: #8b5cf6;
    }}

    .stat-label {{
      font-size: 0.75rem;
      color: #888;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-top: 0.2rem;
    }}

    .container {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 2rem;
    }}

    .company-section {{
      margin-bottom: 2.5rem;
    }}

    .company-name {{
      font-size: 1.3rem;
      font-weight: 600;
      color: #fff;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}

    .badge {{
      background: #6366f1;
      color: #fff;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
    }}

    .job-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1rem;
    }}

    .job-card {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 12px;
      padding: 1.3rem;
      transition: all 0.2s ease;
    }}

    .job-card:hover {{
      background: rgba(255, 255, 255, 0.07);
      border-color: rgba(99, 102, 241, 0.4);
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
    }}

    .job-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
      margin-bottom: 0.6rem;
    }}

    .job-title {{
      font-size: 1rem;
      font-weight: 600;
      color: #fff;
      line-height: 1.3;
    }}

    .job-type {{
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      font-size: 0.7rem;
      font-weight: 500;
      padding: 0.2rem 0.5rem;
      border-radius: 5px;
      white-space: nowrap;
      flex-shrink: 0;
    }}

    .job-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.8rem;
      margin-bottom: 0.8rem;
    }}

    .meta-item {{
      font-size: 0.8rem;
      color: #999;
    }}

    .job-description {{
      font-size: 0.85rem;
      color: #aaa;
      line-height: 1.5;
      margin-bottom: 1rem;
    }}

    .apply-btn {{
      display: inline-block;
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      color: #fff;
      text-decoration: none;
      font-size: 0.85rem;
      font-weight: 500;
      padding: 0.5rem 1rem;
      border-radius: 8px;
      transition: all 0.2s ease;
    }}

    .apply-btn:hover {{
      background: linear-gradient(135deg, #4f46e5, #7c3aed);
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
    }}

    .footer {{
      text-align: center;
      padding: 2rem;
      color: #555;
      font-size: 0.8rem;
    }}

    @media (max-width: 768px) {{
      .header {{ padding: 1.5rem 1rem; }}
      .container {{ padding: 1rem; }}
      .stats {{ gap: 0.8rem; }}
      .stat {{ min-width: 100px; padding: 0.6rem 0.8rem; }}
      .job-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <h1>🔍 <span>Job Scout</span> — Latest Listings</h1>
    <p class="subtitle">Generated on {timestamp}</p>
    <div class="stats">
      <div class="stat">
        <div class="stat-value">{total}</div>
        <div class="stat-label">Total Jobs</div>
      </div>
      <div class="stat">
        <div class="stat-value">{companies_count}</div>
        <div class="stat-label">Companies</div>
      </div>
      <div class="stat">
        <div class="stat-value">{remote_count}</div>
        <div class="stat-label">Remote</div>
      </div>
    </div>
  </div>

  <div class="container">
    {job_cards_html}
  </div>

  <div class="footer">
    Job Scout — Multi-Agent Job Scraper • Generated {timestamp}
  </div>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    return output_path


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
