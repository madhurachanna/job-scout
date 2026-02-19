"""
HTML Report Generator — creates a beautiful static HTML page for job listings.
"""

from datetime import datetime


def generate_html_report(jobs: list[dict], output_path: str) -> str:
    """
    Generate a static HTML page displaying all job listings with a sidebar filter.

    Args:
        jobs: List of standardized job dicts.
        output_path: Path to save the HTML file.

    Returns:
        Path to the generated HTML file.
    """
    timestamp_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    
    # Pre-calculate counts for filters
    total_jobs = len(jobs)
    
    import time
    now_ts = time.time()
    
    count_1h = 0
    count_3h = 0
    count_6h = 0
    count_24h = 0
    count_48h = 0
    
    for job in jobs:
        # Standardize date to timestamp
        date_str = job.get("date_posted")
        ts = 0
        if date_str:
            try:
                # Handle ISO format
                if date_str.endswith("+0000"):
                    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
                else:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                ts = dt.timestamp()
            except (ValueError, TypeError):
                pass
        
        job["_ts"] = ts
        age = now_ts - ts
        
        if age < 3600: count_1h += 1
        if age < 10800: count_3h += 1
        if age < 21600: count_6h += 1
        if age < 86400: count_24h += 1
        if age < 172800: count_48h += 1

    # Group jobs by company
    companies = {}
    for job in jobs:
        company = job.get("company", "Unknown")
        if company not in companies:
            companies[company] = []
        companies[company].append(job)

    # Build Toolbar HTML (Date Filters)
    toolbar_html = f"""
    <div class="toolbar">
      <span class="toolbar-label">Time Posted:</span>
      <button class="toolbar-btn time-filter active" onclick="filterTime(0, this)">
        All Time <span class="badgish">{total_jobs}</span>
      </button>
      <button class="toolbar-btn time-filter" onclick="filterTime(1, this)">
        1h <span class="badgish">{count_1h}</span>
      </button>
      <button class="toolbar-btn time-filter" onclick="filterTime(3, this)">
        3h <span class="badgish">{count_3h}</span>
      </button>
      <button class="toolbar-btn time-filter" onclick="filterTime(6, this)">
        6h <span class="badgish">{count_6h}</span>
      </button>
      <button class="toolbar-btn time-filter" onclick="filterTime(24, this)">
        Today <span class="badgish">{count_24h}</span>
      </button>
      <button class="toolbar-btn time-filter" onclick="filterTime(48, this)">
        2 Days <span class="badgish">{count_48h}</span>
      </button>
      <div class="toolbar-spacer"></div>
      <span class="toolbar-info" id="visible-count">{total_jobs} jobs visible</span>
    </div>
    """

    # Build sidebar HTML (Companies Only)
    sidebar_html = f"""
    <div class="sidebar">
      <div class="filter-group">
        <h3 class="filter-title">Companies</h3>
        <button class="filter-btn comp-filter active" onclick="filterCompany('all', this)">
          <span>All Companies</span>
          <span class="badgish">{len(jobs)}</span>
        </button>
    """
    for company, company_jobs in sorted(companies.items()):
        safe_comp = _esc(company).replace(" ", "-").lower()
        sidebar_html += f"""
        <button class="filter-btn comp-filter" onclick="filterCompany('{safe_comp}', this)">
          <span>{_esc(company)}</span>
          <span class="badgish">{len(company_jobs)}</span>
        </button>
        """
    sidebar_html += "</div></div>"

    # Build job cards HTML
    job_cards_html = '<div class="content-area">'
    for company, company_jobs in sorted(companies.items()):
        safe_comp = _esc(company).replace(" ", "-").lower()
        job_cards_html += f'<div id="section-{safe_comp}" class="company-section" data-comp="{safe_comp}">\n'
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
            ts = job.get("_ts", 0)

            # Format date for display (Local Time)
            date_display = ""
            if date_posted:
                try:
                    if date_posted.endswith("+0000"):
                        dt = datetime.strptime(date_posted, "%Y-%m-%dT%H:%M:%S%z")
                    else:
                        dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
                    
                    # Convert to local system time (EST for user)
                    dt_local = dt.astimezone()
                    date_display = dt_local.strftime("%b %d, %I:%M %p")
                except (ValueError, TypeError):
                    date_display = date_posted

            # Truncate description for card
            desc_short = description[:160] + "..." if len(description) > 160 else description
            
            job_cards_html += f"""    <div class="job-card" data-ts="{ts}">
      <div class="job-header">
        <h3 class="job-title">{title}</h3>
      </div>
      <div class="job-meta">
        {f'<span class="meta-item">📍 {location}</span>' if location else ''}
        {f'<span class="meta-item">📅 {date_display}</span>' if date_display else ''}
      </div>
      <div class="job-tags">
         {f'<span class="tag">{job_type}</span>' if job_type else ''}
         {f'<span class="tag source-tag">{source}</span>' if source else ''}
      </div>
      {f'<a href="{url}" target="_blank" class="apply-link">View Job →</a>' if url else ''}
    </div>
"""
        job_cards_html += '  </div>\n</div>\n'
    job_cards_html += '</div>'

    # Summary stats
    companies_count = len(companies)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Scout — {timestamp_str}</title>
  <style>
    :root {{
      --bg-dark: #0f0f13;
      --bg-panel: #181820;
      --border: #2a2a35;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --text-main: #e0e0e0;
      --text-muted: #9ca3af;
    }}

    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, sans-serif;
      background: var(--bg-dark);
      color: var(--text-main);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}

    /* Header */
    .header {{
      background: var(--bg-panel);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      z-index: 10;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 0.8rem;
    }}

    .brand h1 {{ font-size: 1.25rem; font-weight: 700; color: #fff; }}
    .brand span {{ color: var(--accent); }}
    .subtitle {{ color: var(--text-muted); font-size: 0.85rem; margin-top: 2px; }}

    .stats {{ display: flex; gap: 1.5rem; }}
    .stat {{ display: flex; flex-direction: column; align-items: flex-end; }}
    .stat-val {{ font-size: 1.1rem; font-weight: 700; color: #fff; line-height: 1; }}
    .stat-lbl {{ font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-top: 4px; }}
    
    /* Toolbar (Horizontal Date Filters) */
    .toolbar {{
      background: var(--bg-panel);
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      padding: 0.8rem 2rem;
      display: flex;
      gap: 0.8rem;
      overflow-x: auto;
      align-items: center;
      flex-shrink: 0;
    }}

    .toolbar-label {{
      font-size: 0.75rem;
      text-transform: uppercase;
      color: var(--text-muted);
      letter-spacing: 0.05em;
      font-weight: 600;
      margin-right: 0.5rem;
    }}
    
    .toolbar-btn {{
      background: rgba(255,255,255,0.05);
      border: 1px solid transparent;
      color: var(--text-muted);
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      transition: all 0.2s;
      white-space: nowrap;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .toolbar-btn:hover {{ background: rgba(255,255,255,0.08); color: #fff; }}
    .toolbar-btn.active {{
      background: rgba(99, 102, 241, 0.1);
      color: var(--accent);
      border-color: rgba(99, 102, 241, 0.2);
      font-weight: 600;
      box-shadow: 0 0 10px rgba(99, 102, 241, 0.1);
    }}
    
    .toolbar-spacer {{ flex: 1; }}
    .toolbar-info {{ color: var(--text-muted); font-size: 0.8rem; }}

    /* Layout */
    .main-container {{
      display: grid;
      grid-template-columns: 260px 1fr;
      flex: 1;
      overflow: hidden;
    }}

    /* Sidebar */
    .sidebar {{
      background: var(--bg-panel);
      border-right: 1px solid var(--border);
      padding: 1.5rem;
      overflow-y: auto;
    }}

    .filter-group {{ margin-bottom: 2rem; }}
    .filter-title {{
      font-size: 0.75rem;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 0.8rem;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.4rem;
    }}

    .filter-btn {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-muted);
      padding: 0.5rem 0.8rem;
      margin-bottom: 0.2rem;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      transition: all 0.2s;
      text-align: left;
    }}

    .filter-btn:hover {{ background: rgba(255,255,255,0.03); color: #fff; }}
    .filter-btn.active {{
      background: rgba(99, 102, 241, 0.1);
      color: var(--accent);
      border-color: rgba(99, 102, 241, 0.2);
      font-weight: 600;
    }}

    .badgish {{
      background: rgba(255,255,255,0.05);
      border-radius: 99px;
      padding: 2px 8px;
      font-size: 0.7rem;
    }}
    .filter-btn.active .badgish, .toolbar-btn.active .badgish {{ background: var(--accent); color: #fff; }}

    /* Content Area */
    .content-area {{
      padding: 2rem;
      overflow-y: auto;
      scroll-behavior: smooth;
    }}

    .company-section {{ margin-bottom: 3rem; }}
    .company-name {{
      font-size: 1.1rem;
      color: #fff;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      gap: 0.8rem;
    }}

    .job-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1rem;
    }}

    .job-card {{
      background: rgba(255,255,255,0.02);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.2rem;
      transition: all 0.2s;
      display: flex;
      flex-direction: column;
      position: relative;
    }}

    .job-card:hover {{
      background: rgba(255,255,255,0.04);
      border-color: #444;
      transform: translateY(-2px);
    }}

    .job-title {{
      font-size: 1rem;
      color: #fff;
      font-weight: 600;
      margin-bottom: 0.5rem;
      line-height: 1.35;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .job-meta {{
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 1rem;
      display: flex;
      gap: 1rem;
    }}

    .job-tags {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1rem;
      flex-wrap: wrap;
    }}

    .tag {{
      font-size: 0.7rem;
      background: rgba(255,255,255,0.05);
      padding: 2px 8px;
      border-radius: 4px;
      color: #bbb;
    }}
    .source-tag {{ background: rgba(99,102,241,0.1); color: #a5b4fc; }}

    .apply-link {{
      margin-top: auto;
      font-size: 0.85rem;
      color: var(--accent);
      text-decoration: none;
      font-weight: 500;
      display: flex;
      align-items: center;
    }}
    .apply-link:hover {{ color: var(--accent-hover); }}

    /* Responsive */
    @media (max-width: 800px) {{
      .main-container {{ grid-template-columns: 1fr; }}
      .sidebar {{ display: none; }} /* Mobile menu could be added later */
      .toolbar {{ flex-wrap: wrap; }}
    }}
  </style>
</head>
<body>

  <header class="header">
    <div class="brand">
      <h1>🔍 <span>Job Scout</span></h1>
      <div class="subtitle">Scraped on {timestamp_str}</div>
    </div>
    <div class="stats">
      <div class="stat">
        <span class="stat-val">{total_jobs}</span>
        <span class="stat-lbl">Jobs</span>
      </div>
      <div class="stat">
        <span class="stat-val">{companies_count}</span>
        <span class="stat-lbl">Companies</span>
      </div>
    </div>
  </header>
  
  {toolbar_html}

  <div class="main-container">
    {sidebar_html}
    {job_cards_html}
  </div>

  <script>
    // State
    let currentState = {{
        company: 'all',
        hours: 0, // 0 = all time
    }};

    function filterCompany(companyId, btn) {{
        // Update active class
        document.querySelectorAll('.comp-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        currentState.company = companyId;
        applyFilters();
    }}
    
    function filterTime(hours, btn) {{
        document.querySelectorAll('.time-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        currentState.hours = hours;
        applyFilters();
    }}
    
    function applyFilters() {{
        const allCards = document.querySelectorAll('.job-card');
        const sections = document.querySelectorAll('.company-section');
        const nowTs = Math.floor(Date.now() / 1000);
        let visibleCount = 0;
        
        // Loop all cards and determine visibility
        allCards.forEach(card => {{
            let visible = true;
            
            // Time Filter
            if (currentState.hours > 0) {{
                const ts = parseFloat(card.dataset.ts);
                const age = nowTs - ts;
                if (age > (currentState.hours * 3600)) {{
                    visible = false;
                }}
            }}
            
            card.style.display = visible ? 'flex' : 'none';
            
            // Also check if card belongs to active company filter
            // This is tricky because company filter applies to section.
            // But we need to count total visible cards.
            
            // Actually, we can just do a second pass after hiding sections?
            // Or simpler: check context.
            // Let's assume company filter logic handles section visibility,
            // and we count visible cards in visible sections.
        }});
        
        // Hide empty sections / Show matching company sections
        sections.forEach(section => {{
            // First check company filter
            if (currentState.company !== 'all' && section.dataset.comp !== currentState.company) {{
                section.style.display = 'none';
                return;
            }}
            
            section.style.display = 'block';
            
            // Check if any visible children (filtered by time)
            const visibleCards = section.querySelectorAll('.job-card[style="display: flex;"]');
            if (visibleCards.length === 0) {{
                section.style.display = 'none';
            }} else {{
                visibleCount += visibleCards.length;
            }}
        }});
        
        // Update valid count display
        const countSpan = document.getElementById('visible-count');
        if (countSpan) {{
            countSpan.textContent = visibleCount + ' jobs visible';
        }}
        
        document.querySelector('.content-area').scrollTop = 0;
    }}
  </script>
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
