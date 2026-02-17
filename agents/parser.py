"""
Parser Agent — LLM-powered extraction of job listings from cleaned text.
Uses Qwen3 8B via LM Studio to identify and extract job postings.
"""

import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import settings
from models.state import AgentState


PARSER_SYSTEM_PROMPT = """You are a job listing extractor. Your job is to extract job postings from the provided text content of a career/jobs page.

IMPORTANT INSTRUCTIONS:
1. Extract ONLY actual job postings, not general company info.
2. Return a JSON array of job objects.
3. Each job object must have these fields:
   - "title": job title (string)
   - "company": company name (string)
   - "location": job location (string, use "Not specified" if unknown)
   - "url": direct link to the job if available (string, use "" if not found)
   - "description": brief description of the role (string, 1-2 sentences max)
4. If no jobs are found, return an empty array: []
5. Return ONLY the JSON array, no other text.
6. Do NOT wrap the JSON in markdown code blocks.

/no_think"""

PARSER_USER_PROMPT = """Extract all job postings from the following career page content.
Source: {source_name}
Source URL: {source_url}

Content:
{content}

Return ONLY a JSON array of job objects."""


def _parse_llm_response(response_text: str) -> list[dict]:
    """
    Parse the LLM response into a list of job dicts.
    Handles common LLM output quirks (markdown code blocks, extra text, etc.).
    """
    text = response_text.strip()

    # Remove markdown code blocks if present
    if "```json" in text:
        text = text.split("```json")[-1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Try to find a JSON array in the response
    # Look for content between [ and ]
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            return []
    except json.JSONDecodeError:
        return []


def parser_agent(state: AgentState) -> dict:
    """
    Use LLM to extract job postings from cleaned text.

    Sends the cleaned text to Qwen3 8B with a focused prompt
    to extract structured job data.
    """
    cleaned_text = state.get("cleaned_text", "")
    current_page = state.get("current_page", {})
    source_name = current_page.get("name", "Unknown")
    source_url = current_page.get("url", "")

    # If jobs were already extracted by the scraper (API mode), pass through
    pre_extracted = state.get("extracted_jobs", [])
    if pre_extracted:
        print(f"[Parser] ⏭️  Skipping LLM — {len(pre_extracted)} jobs already extracted via API")
        return {
            "extracted_jobs": pre_extracted,
            "errors": [],
        }

    if not cleaned_text:
        print(f"[Parser] No text to parse for {source_name}")
        return {
            "extracted_jobs": [],
            "errors": [f"No text content to parse for {source_name}"],
        }

    # Truncate text to avoid overwhelming the small model
    if len(cleaned_text) > 4000:
        cleaned_text = cleaned_text[:4000] + "\n\n[... content truncated ...]" 

    print(f"[Parser] Sending {len(cleaned_text)} chars to LLM for extraction...")

    # Initialize the LLM (points to LM Studio)
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key="lm-studio",  # LM Studio doesn't require a real key
        model=settings.llm_model_name,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=120,  # 120s timeout — 8B model can be slow
    )

    # Build the prompt
    messages = [
        SystemMessage(content=PARSER_SYSTEM_PROMPT),
        HumanMessage(
            content=PARSER_USER_PROMPT.format(
                source_name=source_name,
                source_url=source_url,
                content=cleaned_text,
            )
        ),
    ]

    # Call the LLM with retry
    extracted_jobs = []
    max_attempts = 2

    for attempt in range(max_attempts):
        try:
            response = llm.invoke(messages)
            response_text = response.content

            print(f"[Parser] LLM raw response ({len(response_text)} chars):")
            print(f"[Parser]   >>> {response_text[:500]}")

            extracted_jobs = _parse_llm_response(response_text)

            if extracted_jobs:
                print(f"[Parser] Extracted {len(extracted_jobs)} jobs")
                break
            elif attempt < max_attempts - 1:
                print(f"[Parser] No jobs found in response, retrying...")

        except Exception as e:
            error_msg = f"LLM call failed for {source_name}: {str(e)}"
            print(f"[Parser] {error_msg}")
            if attempt == max_attempts - 1:
                return {
                    "extracted_jobs": [],
                    "errors": [error_msg],
                }

    # Add source info to each job
    for job in extracted_jobs:
        job["source"] = source_name
        if not job.get("url") and source_url:
            job["url"] = source_url

    return {
        "extracted_jobs": extracted_jobs,
        "errors": [],
    }
