"""
Normalizer Agent — LLM-powered normalization of extracted job data.
Standardizes formats and validates against the Job Pydantic model.
"""

import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from config.settings import settings
from models.job import Job
from models.state import AgentState


NORMALIZER_SYSTEM_PROMPT = """You are a data normalizer for job listings. Your job is to clean and standardize job data.

INSTRUCTIONS:
1. Standardize location formats (e.g., "NYC" → "New York, NY", "SF" → "San Francisco, CA", "Remote" stays "Remote")
2. Clean job titles (remove extra whitespace, fix capitalization)
3. Ensure company names are properly capitalized
4. Keep descriptions concise (1-2 sentences)
5. Set job_type if detectable from title/description (Full-time, Part-time, Contract, Internship)
6. Return a JSON array of normalized job objects with these fields:
   - "title", "company", "location", "url", "description", "date_posted", "source", "job_type"
7. Return ONLY the JSON array, no other text.
8. Do NOT wrap the JSON in markdown code blocks.

/no_think"""

NORMALIZER_USER_PROMPT = """Normalize the following job listings data. Standardize locations, clean titles, and ensure consistency.

Raw job data:
{jobs_json}

Return ONLY a JSON array of normalized job objects."""


def normalizer_agent(state: AgentState) -> dict:
    """
    Normalize extracted job data using LLM.

    Takes raw extracted jobs, sends them to the LLM for normalization,
    then validates each job against the Pydantic model.
    """
    extracted_jobs = state.get("extracted_jobs", [])
    current_page = state.get("current_page", {})
    source_name = current_page.get("name", "Unknown")

    if not extracted_jobs:
        print(f"[Normalizer] No jobs to normalize for {source_name}")
        return {
            "normalized_jobs": [],
            "errors": [],
        }

    if settings.skip_normalization:
        print(f"[Normalizer] ⏭️  Skipping normalization (requested by user)")
        # Just validate structure and pass through
        validated_jobs = []
        for job_data in extracted_jobs:
            # Ensure minimal fields
            job_data.setdefault("source", source_name)
            job_data.setdefault("job_type", "")
            job_data.setdefault("date_posted", None)
            validated_jobs.append(job_data)
        
        return {
            "normalized_jobs": validated_jobs,
            "errors": [],
        }

    # If source is API, data is likely structured enough to skip expensive normalization
    # Only normalize HTML content which might be messy or malformed
    page_type = current_page.get("type", "career_page")
    
    if page_type == "api":
        print(f"[Normalizer] ⏭️  Skipping LLM normalization for API source: {source_name}")
        # Just validate structure and pass through
        validated_jobs = []
        for job_data in extracted_jobs:
            # Ensure minimal fields
            job_data.setdefault("source", source_name)
            job_data.setdefault("job_type", "")
            job_data.setdefault("date_posted", None)
            validated_jobs.append(job_data)
        
        return {
            "normalized_jobs": validated_jobs,
            "errors": [],
        }

    print(f"[Normalizer] Normalizing {len(extracted_jobs)} jobs from {source_name}...")

    # Initialize the LLM
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key="lm-studio",
        model=settings.llm_model_name,
        temperature=0.3,  # Lower temperature for more consistent normalization
        max_tokens=settings.llm_max_tokens,
        timeout=120,  # 120s timeout — 8B model can be slow
    )

    # Process jobs in batches to avoid hitting context limits
    BATCH_SIZE = 3
    total_jobs = len(extracted_jobs)
    normalized_raw_all = []
    
    for i in range(0, total_jobs, BATCH_SIZE):
        batch = extracted_jobs[i : i + BATCH_SIZE]
        print(f"[Normalizer] Processing batch {i//BATCH_SIZE + 1}/{(total_jobs + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} jobs)...")

        # Build the prompt for this batch
        jobs_json = json.dumps(batch, indent=2)
        messages = [
            SystemMessage(content=NORMALIZER_SYSTEM_PROMPT),
            HumanMessage(
                content=NORMALIZER_USER_PROMPT.format(jobs_json=jobs_json)
            ),
        ]

        try:
            response = llm.invoke(messages)
            response_text = response.content.strip()

            # Parse the response
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[-1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            # Find JSON array
            match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if match:
                response_text = match.group(0)

            batch_normalized = json.loads(response_text)

            if isinstance(batch_normalized, list):
                normalized_raw_all.extend(batch_normalized)
            elif isinstance(batch_normalized, dict):
                normalized_raw_all.append(batch_normalized)
            else:
                # If structure is wrong, fall back to original for this batch
                print(f"[Normalizer] Batch {i//BATCH_SIZE + 1} returned invalid structure, using original data.")
                normalized_raw_all.extend(batch)

        except (json.JSONDecodeError, Exception) as e:
            # If LLM normalization fails for this batch, fall back to basic normalization
            print(f"[Normalizer] Batch {i//BATCH_SIZE + 1} failed: {e}. Using basic normalization for this batch.")
            normalized_raw_all.extend(batch)

    # Validate each job against the Pydantic model
    validated_jobs = []
    for job_data in normalized_raw_all:
        try:
            # Ensure source is set
            job_data.setdefault("source", source_name)
            job_data.setdefault("job_type", "")
            job_data.setdefault("date_posted", None)

            job = Job(**job_data)
            validated_jobs.append(job.model_dump())
        except Exception as e:
            print(f"[Normalizer] Validation failed for job: {e}")
            # Still include the raw data
            validated_jobs.append(job_data)

    print(f"[Normalizer] Normalized {len(validated_jobs)} jobs")

    return {
        "normalized_jobs": validated_jobs,
        "errors": [],
    }
