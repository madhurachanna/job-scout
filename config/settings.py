"""
Configuration settings for the Job Scout system.
Loads values from .env file and provides typed access.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Determine project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # LLM Configuration (LM Studio)
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
    )
    llm_model_name: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_NAME", "qwen3-8b")
    )
    llm_temperature: float = field(
        default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.7"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "2048"))
    )

    # Scraping Configuration
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30"))
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )

    # Paths
    output_dir: str = field(
        default_factory=lambda: os.getenv("OUTPUT_DIR", "output")
    )

    # Feature Flags
    skip_normalization: bool = field(
        default_factory=lambda: os.getenv("SKIP_NORMALIZATION", "false").lower() == "true"
    )


# Singleton instance
settings = Settings()
