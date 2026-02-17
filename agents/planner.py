"""
Planner Agent — loads career pages and creates a scraping plan.
This is a deterministic agent (no LLM needed).
"""

from tools.file_handler import load_career_pages
from models.state import AgentState


def planner_agent(state: AgentState) -> dict:
    """
    Load career pages config and create an ordered scraping plan.

    Reads from state['career_pages'] (raw config list) and produces
    a scraping_plan with processing metadata.
    """
    career_pages = state.get("career_pages", [])

    if not career_pages:
        return {
            "scraping_plan": [],
            "current_page_index": 0,
            "errors": ["No career pages provided. Check config/career_pages.yaml"],
        }

    # Build scraping plan — add processing order and status
    scraping_plan = []
    for i, page in enumerate(career_pages):
        plan_entry = {
            "index": i,
            "name": page.get("name", f"Page {i+1}"),
            "url": page.get("url", ""),
            "type": page.get("type", "career_page"),
            "status": "pending",
        }
        # Pass through optional fields (api_url, keywords, etc.)
        for key in ("api_url", "keywords"):
            if key in page:
                plan_entry[key] = page[key]
        scraping_plan.append(plan_entry)

    print(f"[Planner] Created scraping plan with {len(scraping_plan)} pages:")
    for page in scraping_plan:
        print(f"  - {page['name']}: {page['url']}")

    return {
        "scraping_plan": scraping_plan,
        "current_page_index": 0,
        "current_page": scraping_plan[0] if scraping_plan else {},
        "errors": [],
    }
