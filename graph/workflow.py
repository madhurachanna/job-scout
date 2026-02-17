"""
LangGraph Workflow — defines the agent graph with state transitions.

Graph structure:
    planner → scraper → parser → normalizer → [loop?] → dedup → formatter

The graph loops back from normalizer to scraper when there are more pages
to process, and proceeds to dedup once all pages are done.
"""

from langgraph.graph import StateGraph, END
from models.state import AgentState
from agents.planner import planner_agent
from agents.scraper import scraper_agent
from agents.parser import parser_agent
from agents.normalizer import normalizer_agent
from agents.dedup import dedup_agent
from agents.formatter import formatter_agent


def should_continue(state: AgentState) -> str:
    """
    Conditional edge: decide whether to process the next page or move to dedup.

    Returns:
        'scraper' if more pages remain, 'dedup' if all pages are done.
    """
    scraping_plan = state.get("scraping_plan", [])
    current_index = state.get("current_page_index", 0)

    if current_index < len(scraping_plan) - 1:
        return "scraper"
    else:
        return "dedup"


def advance_to_next_page(state: AgentState) -> dict:
    """
    Transition node: advance to the next page in the scraping plan.
    Updates the current_page_index and current_page.
    """
    scraping_plan = state.get("scraping_plan", [])
    current_index = state.get("current_page_index", 0)
    next_index = current_index + 1

    if next_index < len(scraping_plan):
        print(f"\n[Workflow] Moving to page {next_index + 1}/{len(scraping_plan)}")
        return {
            "current_page_index": next_index,
            "current_page": scraping_plan[next_index],
            # Reset per-page state so the next page starts fresh
            "extracted_jobs": [],
            "raw_html": "",
            "cleaned_text": "",
        }

    return {}


def build_workflow() -> StateGraph:
    """
    Build and compile the LangGraph workflow.

    Returns:
        Compiled StateGraph ready to invoke.
    """
    # Create the graph
    workflow = StateGraph(AgentState)

    # Add nodes (each agent is a node in the graph)
    workflow.add_node("planner", planner_agent)
    workflow.add_node("scraper", scraper_agent)
    workflow.add_node("parser", parser_agent)
    workflow.add_node("normalizer", normalizer_agent)
    workflow.add_node("advance", advance_to_next_page)
    workflow.add_node("dedup", dedup_agent)
    workflow.add_node("formatter", formatter_agent)

    # Define edges (execution flow)
    workflow.set_entry_point("planner")

    # Planner → Scraper
    workflow.add_edge("planner", "scraper")

    # Scraper → Parser
    workflow.add_edge("scraper", "parser")

    # Parser → Normalizer
    workflow.add_edge("parser", "normalizer")

    # Normalizer → conditional: more pages? → advance → scraper  OR  → dedup
    workflow.add_conditional_edges(
        "normalizer",
        should_continue,
        {
            "scraper": "advance",
            "dedup": "dedup",
        },
    )

    # Advance → Scraper (loop back)
    workflow.add_edge("advance", "scraper")

    # Dedup → Formatter
    workflow.add_edge("dedup", "formatter")

    # Formatter → END
    workflow.add_edge("formatter", END)

    # Compile and return
    return workflow.compile()


# Pre-built graph instance
graph = build_workflow()
