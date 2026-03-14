"""
Browser Scraper — uses Playwright to scrape SPA-based career pages.
Extracts structured job data via CSS selectors (no LLM needed).

Supports: Google, Meta, Oracle, PayPal
"""

import time as _time
from datetime import datetime, timezone


# ── Site Configurations ───────────────────────────────────────
# Each config defines CSS selectors and extraction logic per site.

SITE_CONFIGS = {
    "google": {
        "match": "google.com/about/careers",
        "wait_selector": "li.lLd3Je",
        "card_selector": "li.lLd3Je",
        "base_url": "https://www.google.com/about/careers/applications/",
    },
    "meta": {
        "match": "metacareers.com",
        "wait_selector": "a[href*='/profile/job_details/']",
        "card_selector": "a[href*='/profile/job_details/']",
        "base_url": "https://www.metacareers.com",
    },
    "oracle": {
        "match": "careers.oracle.com",
        "wait_selector": "a.job-grid-item__link",
        "card_selector": "a.job-grid-item__link",
        "base_url": "https://careers.oracle.com",
    },
    "paypal": {
        "match": "paypal.eightfold.ai",
        "wait_selector": "a[id^='job-card-']",
        "card_selector": "a[id^='job-card-']",
        "base_url": "https://paypal.eightfold.ai",
    },
}


def _detect_site(url: str) -> dict | None:
    """Detect which site config to use based on URL."""
    for key, config in SITE_CONFIGS.items():
        if config["match"] in url:
            return {**config, "key": key}
    return None


# ── Per-Site Extraction Scripts ───────────────────────────────
# JavaScript functions that run in the browser context to extract job data.

EXTRACT_GOOGLE_JS = """
() => {
    const cards = document.querySelectorAll('li.lLd3Je');
    return Array.from(cards).map(card => {
        const titleEl = card.querySelector('h3.QJPWVe');
        const linkEl = card.querySelector('a.WpHeLc');
        const locEls = card.querySelectorAll('.r0wTof');
        const locations = Array.from(locEls).map(el => el.textContent.trim()).filter(Boolean);
        return {
            title: titleEl ? titleEl.textContent.trim() : '',
            url: linkEl ? linkEl.getAttribute('href') : '',
            location: locations.join('; '),
        };
    }).filter(j => j.title);
}
"""

EXTRACT_META_JS = """
() => {
    const cards = document.querySelectorAll("a[href*='/profile/job_details/']");
    return Array.from(cards).map(card => {
        const titleEl = card.querySelector('h3');
        const href = card.getAttribute('href') || '';
        // Location is typically in a span near the title
        const spans = card.querySelectorAll('span');
        let location = '';
        for (const span of spans) {
            const text = span.textContent.trim();
            // Location spans usually contain a comma (city, state) or specific keywords
            if (text && (text.includes(',') || text.includes('Remote')) && text.length < 100) {
                location = text;
                break;
            }
        }
        return {
            title: titleEl ? titleEl.textContent.trim() : '',
            url: href,
            location: location,
        };
    }).filter(j => j.title);
}
"""

EXTRACT_ORACLE_JS = """
() => {
    const cards = document.querySelectorAll('a.job-grid-item__link');
    return Array.from(cards).map(card => {
        // Oracle card structure: first significant text block is the title
        const allText = card.querySelectorAll('span, div, p');
        let title = '';
        let location = '';
        const texts = [];
        for (const el of allText) {
            const t = el.textContent.trim();
            if (t && t.length > 2 && t.length < 200 && !texts.includes(t)) {
                texts.push(t);
            }
        }
        // First unique text is usually the title
        if (texts.length > 0) title = texts[0];
        // Second or third text is usually the location
        if (texts.length > 1) location = texts[1];

        return {
            title: title,
            url: card.getAttribute('href') || '',
            location: location,
        };
    }).filter(j => j.title);
}
"""

EXTRACT_PAYPAL_JS = """
() => {
    const cards = document.querySelectorAll("a[id^='job-card-']");
    return Array.from(cards).map(card => {
        // Title is typically the first prominent text
        const allDivs = card.querySelectorAll('div');
        let title = '';
        let location = '';
        const seen = new Set();

        for (const div of allDivs) {
            // Only get direct text (not nested children)
            const directText = Array.from(div.childNodes)
                .filter(n => n.nodeType === 3)
                .map(n => n.textContent.trim())
                .join('')
                .trim();

            if (directText && directText.length > 2 && !seen.has(directText)) {
                seen.add(directText);
                if (!title) {
                    title = directText;
                } else if (!location && directText.length < 100) {
                    location = directText;
                }
            }
        }

        // Fallback: try to find location from spans with icon
        if (!location) {
            const locSpans = card.querySelectorAll('span');
            for (const span of locSpans) {
                const t = span.textContent.trim();
                if (t && (t.includes(',') || t.includes('Remote')) && t.length < 100) {
                    location = t;
                    break;
                }
            }
        }

        return {
            title: title,
            url: card.getAttribute('href') || '',
            location: location,
        };
    }).filter(j => j.title);
}
"""

EXTRACT_SCRIPTS = {
    "google": EXTRACT_GOOGLE_JS,
    "meta": EXTRACT_META_JS,
    "oracle": EXTRACT_ORACLE_JS,
    "paypal": EXTRACT_PAYPAL_JS,
}


# ── Pagination Handlers ──────────────────────────────────────

async def _paginate_google(page, max_pages=3):
    """Google Careers uses next-page links with ?page=N."""
    for i in range(max_pages - 1):  # Already loaded page 1
        next_btn = await page.query_selector('a[aria-label="Go to next page"]')
        if not next_btn:
            break
        await next_btn.click()
        await page.wait_for_timeout(3000)


async def _paginate_scroll(page, max_scrolls=5):
    """Infinite scroll pagination (Oracle, PayPal)."""
    for i in range(max_scrolls):
        prev_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == prev_height:
            break


async def _paginate_meta(page, max_clicks=3):
    """Meta has a 'Show more' button."""
    for i in range(max_clicks):
        show_more = await page.query_selector('div[role="button"]')
        if not show_more:
            break
        text = await show_more.text_content()
        if text and "show more" in text.lower():
            await show_more.click()
            await page.wait_for_timeout(3000)
        else:
            break


PAGINATION_HANDLERS = {
    "google": _paginate_google,
    "meta": _paginate_meta,
    "oracle": _paginate_scroll,
    "paypal": _paginate_scroll,
}


# ── Main Entry Point ─────────────────────────────────────────

def scrape_with_browser(url: str, source_name: str) -> list[dict]:
    """
    Scrape a career page using Playwright headless browser.

    Args:
        url: Career page URL to scrape.
        source_name: Name of the company/source.

    Returns:
        List of job dicts with title, company, location, url, source, etc.
    """
    import asyncio

    site = _detect_site(url)
    if not site:
        print(f"[BrowserScraper] ⚠️  No config found for URL: {url}")
        return []

    site_key = site["key"]

    async def _scrape():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--single-process",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--js-flags=--max-old-space-size=256",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            try:
                # Navigate and wait for content

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait for job cards to appear
                wait_sel = site["wait_selector"]
                try:
                    await page.wait_for_selector(wait_sel, timeout=15000)
                except Exception:
                    print(f"[BrowserScraper] ⚠️  Selector {wait_sel} not found after 15s — trying anyway")

                # Extra wait for dynamic content
                await page.wait_for_timeout(3000)

                # Handle cookie banners / popups
                for sel in ['button:has-text("Accept")', 'button:has-text("Accept All")',
                            'button:has-text("I agree")', '[aria-label="Close"]']:
                    try:
                        btn = await page.query_selector(sel)
                        if btn and await btn.is_visible():
                            await btn.click()
                            await page.wait_for_timeout(1000)
                            break
                    except Exception:
                        pass

                # Run pagination to load more results
                paginator = PAGINATION_HANDLERS.get(site_key)
                if paginator:
                    await paginator(page)

                # Extract jobs using site-specific JavaScript
                extract_js = EXTRACT_SCRIPTS[site_key]
                raw_jobs = await page.evaluate(extract_js)


                # Normalize to standard format
                base_url = site.get("base_url", "")
                jobs = []

                for raw in raw_jobs:
                    job_url = raw.get("url", "")
                    # Fix relative URLs
                    if job_url and not job_url.startswith("http"):
                        job_url = base_url.rstrip("/") + "/" + job_url.lstrip("/")

                    jobs.append({
                        "title": raw.get("title", "").strip(),
                        "company": source_name.replace(" Careers", "").replace(" Jobs", "").strip(),
                        "location": raw.get("location", "").strip(),
                        "url": job_url,
                        "description": "",
                        "date_posted": "",  # Not available from job card DOM
                        "source": source_name,
                        "job_type": "Full-time",
                    })

                return jobs

            except Exception as e:
                print(f"[BrowserScraper] ❌ Error scraping {source_name}: {e}")
                return []
            finally:
                await browser.close()

    # Run the async scraper
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(lambda: asyncio.run(_scrape())).result()
            return result
        else:
            return loop.run_until_complete(_scrape())
    except RuntimeError:
        return asyncio.run(_scrape())
