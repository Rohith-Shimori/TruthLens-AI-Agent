"""
TruthLens Inference Configuration

Configures model parameters, retry policies, and rate limiting for the ADK agent pipeline.
"""
import os
import time
import logging
from typing import Optional, Any
from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.workflow._retry_config import RetryConfig

logger = logging.getLogger("TruthLens.Inference")

# Load environment variables
load_dotenv()

# API Configurations
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Model Configuration (configurable via environment)
DEFAULT_MODEL = os.getenv("TRUTHLENS_MODEL", "gemini-2.5-flash")

# Rate limit delay (configurable via environment, default 0.3s)
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "0.3"))

# Define native auto-retry for self-healing agent pipelines
# Targets transient API errors only, not programming errors
agent_retry = RetryConfig(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=10.0,
    backoff_factor=2.0,
    exceptions=[ConnectionError, TimeoutError, OSError]
)

def rate_limit_backoff(*, callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[Any]:
    """Adds a configurable delay before sending requests to the LLM to prevent concurrent burst rate limits on Gemini Free Tier."""
    node_name = callback_context.node.name if (callback_context and callback_context.node) else "unknown"
    logger.info(f"Rate spacing: {RATE_LIMIT_DELAY}s delay before agent '{node_name}'")
    time.sleep(RATE_LIMIT_DELAY)
    return None
