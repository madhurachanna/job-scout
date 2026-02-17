"""
LangGraph Agent State — shared state that flows through the graph.
"""

from typing import TypedDict, Annotated
from models.job import Job


def merge_lists(left: list, right: list) -> list:
    """Reducer that merges two lists (used for accumulating results across loop iterations)."""
    return left + right


def replace_value(left, right):
    """Reducer that replaces the old value with the new one."""
    return right


class AgentState(TypedDict):
    """
    Shared state for the LangGraph workflow.
    Each agent reads from and writes to this state.
    """

    # Input: list of career page configs from YAML
    career_pages: list[dict]

    # Planner output: ordered list of pages to process
    scraping_plan: list[dict]

    # Current page index being processed (for loop control)
    current_page_index: int

    # Current page being scraped
    current_page: dict

    # Scraper output: raw HTML content
    raw_html: str

    # Text extractor output: cleaned text from HTML
    cleaned_text: str

    # Parser output: raw extracted job dicts from LLM
    extracted_jobs: list[dict]

    # Normalizer output: validated Job objects (as dicts for serialization)
    normalized_jobs: Annotated[list[dict], merge_lists]

    # Final output: deduplicated jobs
    final_jobs: list[dict]

    # Accumulated errors during processing
    errors: Annotated[list[str], merge_lists]
