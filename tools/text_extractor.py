"""
Text Extractor Tool — extracts clean text and job-related links from HTML.
Uses BeautifulSoup to strip irrelevant elements.
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def extract_text(html: str, max_length: int = 4000) -> str:
    """
    Extract meaningful text from raw HTML.
    Removes scripts, styles, nav, footer, and other non-content elements.
    Truncates to max_length to stay within LLM context limits.

    Args:
        html: Raw HTML string.
        max_length: Maximum character length of extracted text.

    Returns:
        Cleaned text content.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove elements that don't contain useful content
    for element in soup.find_all(
        ["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"]
    ):
        element.decompose()

    # Try to find the main content area first
    main_content = (
        soup.find("main")
        or soup.find("div", {"role": "main"})
        or soup.find("div", {"id": re.compile(r"(content|main|jobs|careers)", re.I)})
        or soup.find("div", {"class": re.compile(r"(content|main|jobs|careers)", re.I)})
        or soup.body
        or soup
    )

    # Get text and normalize whitespace
    text = main_content.get_text(separator="\n", strip=True)

    # Collapse multiple blank lines into single ones
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)

    # Truncate to fit within LLM context
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[... content truncated ...]"

    return text


def extract_job_links(html: str, base_url: str) -> list[dict]:
    """
    Extract links that likely point to job postings.

    Args:
        html: Raw HTML string.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with 'text' and 'url' keys.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Patterns that suggest a link is a job posting
    job_patterns = re.compile(
        r"(job|career|position|opening|role|apply|hiring|vacancy)",
        re.IGNORECASE,
    )

    job_links = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True)

        # Resolve relative URLs
        full_url = urljoin(base_url, href)

        # Skip if already seen, or if it's a non-HTTP link
        if full_url in seen_urls or not full_url.startswith("http"):
            continue

        # Check if the link text or URL looks job-related
        if job_patterns.search(text) or job_patterns.search(href):
            seen_urls.add(full_url)
            job_links.append({
                "text": text[:200],  # Truncate long link text
                "url": full_url,
            })

    return job_links
