"""
Job data model — represents a single job posting.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Job(BaseModel):
    """Represents a single job posting extracted from a career page."""

    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str = Field(default="", description="Job location (city, state, remote, etc.)")
    url: str = Field(default="", description="Direct URL to the job posting")
    description: str = Field(default="", description="Brief job description or summary")
    date_posted: Optional[str] = Field(default=None, description="Date the job was posted")
    source: str = Field(default="", description="Source career page name")
    job_type: str = Field(default="", description="Full-time, Part-time, Contract, etc.")

    def dedup_key(self) -> str:
        """Generate a deduplication key based on core fields."""
        return f"{self.title.lower().strip()}|{self.company.lower().strip()}|{self.location.lower().strip()}"
