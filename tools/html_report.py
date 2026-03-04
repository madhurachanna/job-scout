"""
HTML Report Generator — creates a beautiful static HTML page for job listings.
"""

from datetime import datetime


def generate_html_report(jobs: list[dict], output_path: str, new_keys: set = None) -> str:
    """
    Generate a static HTML page displaying all job listings with a sidebar filter.

    Args:
        jobs: List of standardized job dicts.
        output_path: Path to save the HTML file.
        new_keys: Optional set of dedup keys (title|company|location) for jobs
                  discovered in the latest scrape. These get a NEW badge and
                  trigger the "N new jobs" banner.

    Returns:
        Path to the generated HTML file.
    """
    timestamp_str = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    new_keys = new_keys or set()
    new_count = len(new_keys)
    
    # Pre-calculate counts for filters
    total_jobs = len(jobs)

    # Build new-jobs banner HTML
    if new_count > 0:
        label = "1 new job" if new_count == 1 else f"{new_count} new jobs"
        new_banner_html = f"""
    <div class="new-banner" id="new-banner">
      <span>🆕 {label} since last refresh</span>
      <button class="banner-close" onclick="document.getElementById('new-banner').style.display='none'" title="Dismiss">✕</button>
    </div>"""
    else:
        new_banner_html = ""
    
    import time
    now_ts = time.time()
    
    count_1h = 0
    count_3h = 0
    count_6h = 0
    count_24h = 0
    count_48h = 0
    
    count_no_date = 0

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

        # Only count jobs with a valid date in time-based filters
        if ts == 0:
            count_no_date += 1
            continue

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
      <div class="search-wrapper">
        <input type="text" id="search-box" class="search-box" placeholder="🔍 Search job titles..." oninput="handleSearch(this.value)">
        <button class="search-clear" id="search-clear" onclick="clearSearch()" title="Clear search">✕</button>
      </div>
      <span class="toolbar-info" id="visible-count">{total_jobs} jobs visible</span>
    </div>
    """

    # Build sidebar HTML (Companies Only)
    new_tab_btn_html = ""
    if new_count > 0:
        new_tab_btn_html = f"""
        <button class="filter-btn new-tab-btn" id="new-tab-btn" onclick="filterNew(this)">
          <span>🆕 New</span>
          <span class="badgish new-badgish">{new_count}</span>
        </button>"""

    sidebar_html = f"""
    <div class="sidebar">
      <div class="filter-group">
        <h3 class="filter-title">View</h3>
        {new_tab_btn_html}
      </div>
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
            else:
                date_display = "Date unknown"

            # Truncate description for card
            desc_short = description[:160] + "..." if len(description) > 160 else description
            
            card_href = f'href="{url}" ' if url else ''
            card_target = 'target="_blank" ' if url else ''

            # Check if this job is new
            job_dedup_key = f"{job.get('title','').lower().strip()}|{job.get('company','').lower().strip()}|{job.get('location','').lower().strip()}"
            is_new = job_dedup_key in new_keys
            new_badge = '<span class="new-badge">New</span>' if is_new else ''

            new_attr = 'data-new="1"' if is_new else 'data-new="0"'
            job_cards_html += f"""    <a {card_href}{card_target}class="job-card" data-ts="{ts}" {new_attr}>
      <div class="job-header">
        <h3 class="job-title">{title}{new_badge}</h3>
      </div>
      <div class="job-meta">
        {f'<span class="meta-item">📍 {location}</span>' if location else ''}
        {f'<span class="meta-item">📅 {date_display}</span>' if date_display else ''}
      </div>
      <div class="job-tags">
         {f'<span class="tag">{job_type}</span>' if job_type else ''}
         {f'<span class="tag source-tag">{source}</span>' if source else ''}
      </div>
    </a>
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
      --bg-dark: #111111;
      --bg-panel: #1a1a1a;
      --bg-panel2: #1f1f1f;
      --border: #2e2e2e;
      --accent: #f97316;
      --accent-2: #fb923c;
      --accent-hover: #ea580c;
      --accent-glow: rgba(249, 115, 22, 0.22);
      --text-main: #ffffff;
      --text-muted: #c0c0cc;
      --card-bg: rgba(255,255,255,0.035);
      --card-bg-hover: rgba(249, 115, 22, 0.07);
      --card-border-hover: rgba(249, 115, 22, 0.45);
      --tag-bg: rgba(249, 115, 22, 0.12);
      --tag-color: #fdba74;
      --filter-btn-bg: rgba(255,255,255,0.05);
      --filter-btn-hover: rgba(249, 115, 22, 0.1);
      --toolbar-btn-hover: rgba(249, 115, 22, 0.1);
      --source-tag-bg: rgba(249, 115, 22, 0.13);
      --source-tag-color: #fb923c;
    }}

    [data-theme="light"] {{
      --bg-dark: #f5f5f5;
      --bg-panel: #ffffff;
      --bg-panel2: #fafafa;
      --border: #e5e5e5;
      --accent: #ea580c;
      --accent-2: #f97316;
      --accent-hover: #c2410c;
      --accent-glow: rgba(234, 88, 12, 0.15);
      --text-main: #111111;
      --text-muted: #555555;
      --card-bg: #ffffff;
      --card-bg-hover: #fff7ed;
      --card-border-hover: #fdba74;
      --tag-bg: #fff7ed;
      --tag-color: #c2410c;
      --filter-btn-bg: #f5f5f5;
      --filter-btn-hover: #fff7ed;
      --toolbar-btn-hover: #fff7ed;
      --source-tag-bg: rgba(249,115,22,0.1);
      --source-tag-color: #ea580c;
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

    .stats {{ display: flex; gap: 1.5rem; align-items: center; }}
    .stat {{ display: flex; flex-direction: column; align-items: flex-end; }}
    .stat-val {{ font-size: 1.1rem; font-weight: 700; color: var(--text-main); line-height: 1; }}
    .stat-lbl {{ font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-top: 4px; }}

    /* Theme Toggle */
    .theme-toggle {{
      background: var(--filter-btn-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      width: 36px; height: 36px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 1.1rem;
      display: flex; align-items: center; justify-content: center;
      transition: all 0.2s;
    }}
    .theme-toggle:hover {{ background: var(--filter-btn-hover); color: var(--text-main); }}

    /* Refresh Button */
    .refresh-btn {{
      background: linear-gradient(135deg, var(--accent), var(--accent-hover));
      color: #fff; border: none;
      padding: 0.5rem 1.2rem;
      border-radius: 8px; font-size: 0.85rem;
      cursor: pointer; font-weight: 600;
      transition: all 0.25s;
      display: none; /* Hidden until server detected */
      align-items: center; gap: 6px;
    }}
    .refresh-btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 15px var(--accent-glow); }}
    .refresh-btn:disabled {{ opacity: 0.6; cursor: not-allowed; transform: none; box-shadow: none; }}
    .refresh-btn .spinner {{
      display: inline-block; width: 14px; height: 14px;
      border: 2px solid rgba(255,255,255,0.3);
      border-top-color: #fff; border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

    /* New-jobs Banner */
    .new-banner {{
      background: linear-gradient(135deg, var(--accent), var(--accent-hover));
      color: #fff;
      padding: 0.65rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.9rem;
      font-weight: 600;
      letter-spacing: 0.01em;
      flex-shrink: 0;
      animation: slideDown 0.4s ease;
    }}
    @keyframes slideDown {{
      from {{ transform: translateY(-100%); opacity: 0; }}
      to   {{ transform: translateY(0);    opacity: 1; }}
    }}
    .banner-close {{
      background: rgba(255,255,255,0.2);
      border: none; color: #fff;
      width: 24px; height: 24px;
      border-radius: 50%; cursor: pointer;
      font-size: 0.8rem; font-weight: 700;
      display: flex; align-items: center; justify-content: center;
      transition: background 0.2s;
    }}
    .banner-close:hover {{ background: rgba(255,255,255,0.35); }}

    /* NEW badge on job cards */
    .new-badge {{
      display: inline-block;
      background: var(--accent);
      color: #fff;
      font-size: 0.6rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      padding: 2px 6px;
      border-radius: 4px;
      vertical-align: middle;
      text-transform: uppercase;
      margin-left: 4px;
      flex-shrink: 0;
    }}

    /* New tab button in sidebar */
    .new-badgish {{
      background: var(--accent) !important;
      color: #fff !important;
    }}
    .new-tab-btn {{
      border: 1px solid rgba(249,115,22,0.3);
      color: var(--accent) !important;
      font-weight: 600;
    }}
    .new-tab-btn:hover {{
      background: rgba(249,115,22,0.12) !important;
      border-color: var(--accent) !important;
    }}
    .new-tab-btn.active {{
      background: rgba(249,115,22,0.18) !important;
      border-color: var(--accent) !important;
      box-shadow: 0 0 12px rgba(249,115,22,0.25);
    }}

    /* Disabled state for time filters when New mode is active */
    .new-mode-active .time-filter {{
      opacity: 0.3;
      pointer-events: none;
      cursor: not-allowed;
    }}
    .new-mode-active .toolbar-label {{
      opacity: 0.3;
    }}

    
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
      background: var(--filter-btn-bg);
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
    .toolbar-btn:hover {{ background: var(--toolbar-btn-hover); color: var(--text-main); }}
    .toolbar-btn.active {{
      background: rgba(99, 102, 241, 0.1);
      color: var(--accent);
      border-color: rgba(99, 102, 241, 0.2);
      font-weight: 600;
      box-shadow: 0 0 10px rgba(99, 102, 241, 0.1);
    }}
    
    .toolbar-spacer {{ flex: 1; }}
    .toolbar-info {{ color: var(--text-muted); font-size: 0.8rem; }}

    /* Search Box */
    .search-box {{
      background: var(--filter-btn-bg);
      border: 1px solid var(--border);
      color: var(--text-main);
      padding: 0.4rem 0.8rem;
      padding-right: 2rem;
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
      transition: all 0.2s;
      min-width: 200px;
      font-family: inherit;
    }}
    .search-box::placeholder {{ color: var(--text-muted); opacity: 0.6; }}
    .search-box:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
    }}
    .search-wrapper {{
      position: relative;
      display: flex;
      align-items: center;
    }}
    .search-clear {{
      position: absolute;
      right: 6px;
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.85rem;
      padding: 2px 4px;
      border-radius: 4px;
      line-height: 1;
      display: none;
      transition: color 0.2s;
    }}
    .search-clear:hover {{ color: var(--text-main); }}

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

    .filter-btn:hover {{ background: var(--filter-btn-hover); color: var(--text-main); }}
    .filter-btn.active {{
      background: rgba(99, 102, 241, 0.1);
      color: var(--accent);
      border-color: rgba(99, 102, 241, 0.2);
      font-weight: 600;
    }}

    .badgish {{
      background: var(--tag-bg);
      border-radius: 99px;
      padding: 2px 8px;
      font-size: 0.7rem;
      color: var(--tag-color);
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
      color: var(--text-main);
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 2px solid;
      border-image: linear-gradient(90deg, var(--accent), transparent) 1;
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
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.2rem;
      transition: all 0.2s;
      display: flex;
      flex-direction: column;
      position: relative;
      text-decoration: none;
      color: inherit;
      cursor: pointer;
    }}

    .job-card:hover {{
      background: var(--card-bg-hover);
      border-color: var(--card-border-hover);
      box-shadow: 0 4px 24px var(--accent-glow);
      transform: translateY(-2px);
    }}

    .job-title {{
      font-size: 1rem;
      color: var(--text-main);
      font-weight: 600;
      margin-bottom: 0.5rem;
      line-height: 1.35;
      letter-spacing: 0.018em;
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
      background: var(--tag-bg);
      padding: 2px 8px;
      border-radius: 4px;
      color: var(--tag-color);
    }}
    .source-tag {{ background: var(--source-tag-bg); color: var(--source-tag-color); }}

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
        <span class="stat-val" id="header-job-count">{total_jobs}</span>
        <span class="stat-lbl">Jobs</span>
      </div>
      <div class="stat">
        <span class="stat-val" id="header-company-count">{companies_count}</span>
        <span class="stat-lbl">Companies</span>
      </div>
      <button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()" title="Toggle theme">🌙</button>
      <button class="refresh-btn" id="refresh-btn" onclick="startRefresh()">
        🔄 Refresh
      </button>
    </div>
  </header>
  
  {new_banner_html}
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
        searchQuery: '',
        newOnly: false,
    }};

    let searchTimer = null;
    function handleSearch(value) {{
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {{
            currentState.searchQuery = value.toLowerCase().trim();
            const clearBtn = document.getElementById('search-clear');
            if (clearBtn) clearBtn.style.display = value.length > 0 ? 'block' : 'none';
            applyFilters();
        }}, 150);
    }}

    function clearSearch() {{
        const input = document.getElementById('search-box');
        if (input) input.value = '';
        currentState.searchQuery = '';
        const clearBtn = document.getElementById('search-clear');
        if (clearBtn) clearBtn.style.display = 'none';
        applyFilters();
    }}

    function filterNew(btn) {{
        const isActive = !btn.classList.contains('active');
        btn.classList.toggle('active', isActive);
        currentState.newOnly = isActive;

        // Apply/remove the disabled-filters class to body
        document.body.classList.toggle('new-mode-active', isActive);

        if (isActive) {{
            // Reset company & time filter visuals
            currentState.company = 'all';
            currentState.hours = 0;
            currentState.searchQuery = '';
            document.querySelectorAll('.comp-filter').forEach(b => b.classList.remove('active'));
            const allCompBtn = document.querySelector('.comp-filter');
            if (allCompBtn) allCompBtn.classList.add('active');
            document.querySelectorAll('.time-filter').forEach(b => b.classList.remove('active'));
            const allTimeBtn = document.querySelector('.time-filter');
            if (allTimeBtn) allTimeBtn.classList.add('active');
            const searchBox = document.getElementById('search-box');
            if (searchBox) searchBox.value = '';
            const clearBtn = document.getElementById('search-clear');
            if (clearBtn) clearBtn.style.display = 'none';
        }}
        applyFilters();
    }}

    function _deactivateNewTab() {{
        const newBtn = document.getElementById('new-tab-btn');
        if (newBtn && newBtn.classList.contains('active')) {{
            newBtn.classList.remove('active');
            currentState.newOnly = false;
            document.body.classList.remove('new-mode-active');
        }}
    }}

    function filterCompany(companyId, btn) {{
        // Update active class (stays in New mode if active)
        document.querySelectorAll('.comp-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        currentState.company = companyId;
        applyFilters();
    }}
    
    function filterTime(hours, btn) {{
        _deactivateNewTab();
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

            // New-only mode: show only new jobs, skip all other filters
            if (currentState.newOnly) {{
                visible = card.dataset.new === '1';
                card.style.display = visible ? 'flex' : 'none';
                return;
            }}
            
            // Time Filter
            if (currentState.hours > 0) {{
                const ts = parseFloat(card.dataset.ts);
                const age = nowTs - ts;
                if (age > (currentState.hours * 3600)) {{
                    visible = false;
                }}
            }}

            // Search Filter — match against job title
            if (visible && currentState.searchQuery) {{
                const titleEl = card.querySelector('.job-title');
                const title = titleEl ? titleEl.textContent.toLowerCase() : '';
                if (!title.includes(currentState.searchQuery)) {{
                    visible = false;
                }}
            }}
            
            card.style.display = visible ? 'flex' : 'none';
        }});
        
        // Hide empty sections / Show matching company sections
        sections.forEach(section => {{
            // Apply company filter (works in both normal and newOnly mode)
            if (currentState.company !== 'all' && section.dataset.comp !== currentState.company) {{
                section.style.display = 'none';
                return;
            }}
            
            section.style.display = 'block';
            
            // Check if any visible children
            const visibleCards = section.querySelectorAll('.job-card[style="display: flex;"]');
            if (visibleCards.length === 0) {{
                section.style.display = 'none';
            }} else {{
                visibleCount += visibleCards.length;
            }}
        }});
        
        // Update visible count in toolbar and header
        const countSpan = document.getElementById('visible-count');
        if (countSpan) countSpan.textContent = visibleCount + ' jobs visible';
        updateHeaderCount(visibleCount);

        document.querySelector('.content-area').scrollTop = 0;
    }}

    function updateHeaderCount(count) {{
        const el = document.getElementById('header-job-count');
        if (el) el.textContent = count;
        // Also update visible company count
        const compEl = document.getElementById('header-company-count');
        if (compEl) {{
            const visibleSections = document.querySelectorAll('.company-section:not([style*="display: none"])');
            compEl.textContent = visibleSections.length;
        }}
    }}

    // ── Theme Toggle ────────────────────────────────────────
    function toggleTheme() {{
      const isDark = !document.body.hasAttribute('data-theme');
      if (isDark) {{
        document.body.setAttribute('data-theme', 'light');
        document.getElementById('theme-toggle').textContent = '☀️';
        localStorage.setItem('js-theme', 'light');
      }} else {{
        document.body.removeAttribute('data-theme');
        document.getElementById('theme-toggle').textContent = '🌙';
        localStorage.setItem('js-theme', 'dark');
      }}
    }}

    // Restore saved theme and sync counts on load
    (function restoreTheme() {{
      const saved = localStorage.getItem('js-theme');
      if (saved === 'light') {{
        document.body.setAttribute('data-theme', 'light');
        document.getElementById('theme-toggle').textContent = '☀️';
      }}
      // Sync header counts to match what's actually visible
      applyFilters();
    }})();

    // ── Server-aware Refresh ────────────────────────────────
    (function detectServer() {{
      fetch('/api/status')
        .then(r => r.json())
        .then(data => {{
          const btn = document.getElementById('refresh-btn');
          if (btn) {{
            btn.style.display = 'flex';
            if (data.running) {{
              btn.disabled = true;
              btn.innerHTML = '<span class="spinner"></span> Scraping...';
              pollStatus();
            }}
          }}
        }})
        .catch(() => {{}});  // Not served from server — hide button
    }})();

    function startRefresh() {{
      const btn = document.getElementById('refresh-btn');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Scraping...';

      fetch('/api/refresh', {{ method: 'POST' }})
        .then(r => r.json())
        .then(data => {{
          if (data.status === 'already_running') {{
            // Already in progress, just poll
          }}
          pollStatus();
        }})
        .catch(err => {{
          btn.innerHTML = '❌ Error';
          setTimeout(() => {{
            btn.innerHTML = '🔄 Refresh';
            btn.disabled = false;
          }}, 3000);
        }});
    }}

    function pollStatus() {{
      const poll = setInterval(() => {{
        fetch('/api/status')
          .then(r => r.json())
          .then(data => {{
            if (!data.running) {{
              clearInterval(poll);
              const btn = document.getElementById('refresh-btn');
              if (data.last_error) {{
                btn.innerHTML = '❌ Failed';
                setTimeout(() => {{
                  btn.innerHTML = '🔄 Refresh';
                  btn.disabled = false;
                }}, 3000);
              }} else {{
                btn.innerHTML = '✅ Done!';
                setTimeout(() => window.location.reload(), 800);
              }}
            }}
          }});
      }}, 2000);
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
