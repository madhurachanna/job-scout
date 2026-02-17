"""
Web Scraper Tool — fetches raw HTML from URLs.
Uses httpx with proper headers, timeouts, and retry logic.
"""

import httpx
import time
from config.settings import settings


# Common browser-like headers to avoid being blocked
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def fetch_page(url: str, timeout: int = None, max_retries: int = None) -> dict:
    """
    Fetch a web page and return its HTML content.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds (defaults to settings.request_timeout).
        max_retries: Number of retry attempts (defaults to settings.max_retries).

    Returns:
        dict with keys:
            - success (bool): Whether the fetch was successful.
            - html (str): The raw HTML content (empty string on failure).
            - status_code (int): HTTP status code (0 on connection error).
            - error (str): Error message if failed (empty string on success).
            - url (str): The URL that was fetched.
    """
    timeout = timeout or settings.request_timeout
    max_retries = max_retries or settings.max_retries

    for attempt in range(max_retries):
        try:
            with httpx.Client(
                headers=DEFAULT_HEADERS,
                timeout=timeout,
                follow_redirects=True,
                verify=False,  # Skip SSL verification (common macOS Python issue)
            ) as client:
                response = client.get(url)

                if response.status_code == 200:
                    return {
                        "success": True,
                        "html": response.text,
                        "status_code": response.status_code,
                        "error": "",
                        "url": url,
                    }
                else:
                    error_msg = f"HTTP {response.status_code} for {url}"
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return {
                        "success": False,
                        "html": "",
                        "status_code": response.status_code,
                        "error": error_msg,
                        "url": url,
                    }

        except httpx.TimeoutException:
            error_msg = f"Timeout after {timeout}s for {url}"
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {
                "success": False,
                "html": "",
                "status_code": 0,
                "error": error_msg,
                "url": url,
            }

        except httpx.HTTPError as e:
            error_msg = f"HTTP error for {url}: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {
                "success": False,
                "html": "",
                "status_code": 0,
                "error": error_msg,
                "url": url,
            }

    # Should not reach here, but just in case
    return {
        "success": False,
        "html": "",
        "status_code": 0,
        "error": f"All {max_retries} retries exhausted for {url}",
        "url": url,
    }
