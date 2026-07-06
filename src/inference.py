import os
import time
from typing import Optional, Any
from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.workflow._retry_config import RetryConfig

# Load environment variables
load_dotenv()

# API Configurations
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Model Configuration
DEFAULT_MODEL = "gemini-2.5-flash"

# Define native auto-retry for self-healing agent pipelines
agent_retry = RetryConfig(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=10.0,
    backoff_factor=2.0,
    exceptions=[Exception]
)

def rate_limit_backoff(*, callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[Any]:
    """Adds a brief delay of 0.8 seconds before sending requests to the LLM to prevent concurrent burst rate limits on Gemini Free Tier."""
    node_name = callback_context.node.name if (callback_context and callback_context.node) else "unknown"
    print(f"[TruthLens] Rate spacing: sleeping for 0.8s before calling model in agent '{node_name}'...")
    time.sleep(0.8)
    return None
