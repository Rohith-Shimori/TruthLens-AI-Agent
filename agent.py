import os
import json
import time
from typing import List, Dict, Any, Generator, Optional
from google.adk import Agent, Workflow, Runner, Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest

from config import DEFAULT_MODEL, GOOGLE_API_KEY
from tools import scrape_url, search_google_grounding, search_wikipedia, extract_text_from_image
from credibility import CredibilityScorer
from bias_analyzer import BiasAnalyzer

# Initialize helpers
cred_scorer = CredibilityScorer()
bias_anal = BiasAnalyzer()

def rate_limit_backoff(*, callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[Any]:
    """Adds a delay of 4.0 seconds before sending requests to the LLM to avoid Gemini Free Tier rate limits (15 RPM)."""
    print(f"[TruthLens] Rate limit backoff: sleeping for 4.0s before calling model in agent '{callback_context.node.name}'...")
    time.sleep(4.0)
    return None


# Define tools as callable functions for the agents
# ADK will parse docstrings to generate function schemas for the LLM

def analyze_source_credibility_tool(urls: List[str]) -> str:
    """
    Computes credibility scores for a list of URLs or domain names.
    Args:
        urls: List of URL strings to analyze.
    Returns:
        JSON string containing the credibility assessment.
    """
    res = cred_scorer.aggregate_credibility(urls)
    return json.dumps(res, indent=2)

def analyze_bias_tool(text: str) -> str:
    """
    Analyzes a text block for emotional language and sensationalism.
    Args:
        text: The text string to analyze.
    Returns:
        JSON string containing sensationalism ratings.
    """
    res = bias_anal.analyze_bias_local(text)
    return json.dumps(res, indent=2)


# ==========================================
# 1. INGESTION AGENT
# ==========================================
ingestion_agent = Agent(
    name="IngestionAgent",
    model=DEFAULT_MODEL,
    instruction=(
        "You are the IngestionAgent of TruthLens. Your role is to receive user input (which can be a URL, "
        "raw text, or an image file path) and extract the core text content to be verified.\n"
        "Rules:\n"
        "1. If the input is a valid URL, use the 'scrape_url' tool to fetch the page content.\n"
        "2. If the input looks like an image file path (ends with .jpg, .png, etc.), use the 'extract_text_from_image' tool to get the OCR text.\n"
        "3. If the input is raw text, output it directly.\n"
        "Your final response MUST be a clean JSON block containing:\n"
        " - input_type: 'url', 'image', or 'text'\n"
        " - title: title of the page or a short summary header for text/image\n"
        " - content: the extracted raw text to be fact-checked.\n"
        "Ensure your output is structured as JSON."
    ),
    tools=[scrape_url, extract_text_from_image],
    before_model_callback=rate_limit_backoff
)

# ==========================================
# 2. CLAIM EXTRACTION AGENT
# ==========================================
claim_extractor_agent = Agent(
    name="ClaimExtractionAgent",
    model=DEFAULT_MODEL,
    instruction=(
        "You are the ClaimExtractionAgent of TruthLens. Your role is to read the extracted content "
        "provided by the IngestionAgent and isolate the key, verifiable factual claims.\n"
        "Rules:\n"
        "1. Ignore opinions, feelings, or general comments. Focus only on statements that can be proven true or false "
        "(e.g., statistics, events, quotes, policy claims, historical claims).\n"
        "2. Extract up to 3 core claims.\n"
        "3. Your final response MUST be a JSON object containing a list of claims, where each claim has a unique ID, "
        "the claim text, and why it is check-worthy."
    ),
    before_model_callback=rate_limit_backoff
)

# ==========================================
# 3. EVIDENCE RETRIEVER AGENT
# ==========================================
evidence_retriever_agent = Agent(
    name="EvidenceRetrieverAgent",
    model=DEFAULT_MODEL,
    instruction=(
        "You are the EvidenceRetrieverAgent of TruthLens. Your role is to verify the extracted claims "
        "by searching for supporting or refuting evidence.\n"
        "Rules:\n"
        "1. For each claim, use the 'search_google_grounding' and 'search_wikipedia' tools to look up facts.\n"
        "2. Retrieve relevant quotes, statistics, and articles, noting their URLs and publisher titles.\n"
        "3. Your final response MUST list the claims along with the compiled evidence (with URLs and snippets) for each claim."
    ),
    tools=[search_google_grounding, search_wikipedia],
    before_model_callback=rate_limit_backoff
)

# ==========================================
# 4. SOURCE CREDIBILITY AGENT
# ==========================================
credibility_scorer_agent = Agent(
    name="SourceCredibilityAgent",
    model=DEFAULT_MODEL,
    instruction=(
        "You are the SourceCredibilityAgent of TruthLens. Your role is to assess the reliability of the sources "
        "found by the EvidenceRetrieverAgent.\n"
        "Rules:\n"
        "1. Collect the URLs of all source articles cited by the EvidenceRetrieverAgent.\n"
        "2. Use the 'analyze_source_credibility_tool' to get ratings and classifications for these domains.\n"
        "3. Provide a summary explaining which sources are highly trusted (e.g., Reuters, Wikipedia) and which are "
        "questionable or user-generated (e.g., social media, blogs).\n"
        "4. Your final response MUST be a structured assessment of the sources."
    ),
    tools=[analyze_source_credibility_tool],
    before_model_callback=rate_limit_backoff
)

# ==========================================
# 5. BIAS & SENTIMENT AGENT
# ==========================================
bias_analyzer_agent = Agent(
    name="BiasAnalyzerAgent",
    model=DEFAULT_MODEL,
    instruction=(
        "You are the BiasAnalyzerAgent of TruthLens. Your role is to evaluate the tone, loaded language, "
        "logical fallacies, and potential ideological framing in the original text.\n"
        "Rules:\n"
        "1. Use the 'analyze_bias_tool' to run local heuristic sensationalism and sentiment scores on the original text.\n"
        "2. Perform a qualitative analysis of logical fallacies (e.g., appeal to emotion, strawman) and political bias.\n"
        "3. Your final response MUST contain the sensationalism score, detected fallacies, and a brief description of the writing style's objectivity."
    ),
    tools=[analyze_bias_tool],
    before_model_callback=rate_limit_backoff
)

# ==========================================
# 6. VERDICT AGENT
# ==========================================
verdict_agent = Agent(
    name="VerdictAgent",
    model=DEFAULT_MODEL,
    instruction=(
        "You are the VerdictAgent of TruthLens. Your role is to cross-reference the claims, evidence, and source credibility "
        "ratings to determine the veracity of the claims.\n"
        "Rules:\n"
        "1. For each claim, issue one of the following verdicts:\n"
        "   - True: Claim is fully supported by credible evidence.\n"
        "   - Mostly True: Claim is accurate in essence, but has minor context gaps.\n"
        "   - Misleading: Claim contains elements of truth but is presented in a way to deceive.\n"
        "   - False: Claim is directly contradicted by reliable evidence.\n"
        "   - Unverified: There is not enough reliable evidence to prove or disprove the claim.\n"
        "2. Calculate a confidence score (0 to 100) based on source reliability and evidence match.\n"
        "3. Your final response MUST contain the structured verdict for each claim, the overall confidence score, and a clear rationale."
    ),
    before_model_callback=rate_limit_backoff
)

# ==========================================
# 7. REPORT GENERATOR AGENT
# ==========================================
report_generator_agent = Agent(
    name="ReportGeneratorAgent",
    model=DEFAULT_MODEL,
    instruction=(
        "You are the ReportGeneratorAgent of TruthLens. Your role is to synthesize the findings from all previous "
        "agents and write a beautiful, comprehensive, and objective markdown report for the user.\n"
        "The report MUST follow this layout:\n"
        "1. Title: 🛡️ TruthLens Fact-Check Report\n"
        "2. Final Verdict Banner: Large header indicating the overall verdict (True, Mostly True, Misleading, False, Unverified) "
        "with an emoji and a confidence score percentage.\n"
        "3. Executive Summary: A concise, 2-3 sentence overview of what the claim is and the result of the investigation.\n"
        "4. Claims & Evidence Breakdown: A list of the extracted claims. For each claim, provide a bulleted list of evidence with "
        "source links/titles and its individual verdict.\n"
        "5. Source Credibility Assessment: Summarize the credibility of the sources, listing trusted and untrusted links with score.\n"
        "6. Bias & Sensationalism Analysis: Detail the sensationalism score, emotional loading, and logical fallacies.\n"
        "7. Digital Literacy Guidance: Provide actionable advice on how to spot this specific type of misinformation "
        "(especially if it's typical of fast-spreading social media/WhatsApp rumors).\n"
        "Format your entire output as standard Markdown."
    ),
    before_model_callback=rate_limit_backoff
)


# ==========================================
# WORKFLOW ORCHESTRATION
# ==========================================

# Define the sequential path in ADK 2.0
truthlens_workflow = Workflow(
    name="TruthLensVerificationPipeline",
    edges=[(
        "START",
        ingestion_agent,
        claim_extractor_agent,
        evidence_retriever_agent,
        credibility_scorer_agent,
        bias_analyzer_agent,
        verdict_agent,
        report_generator_agent
    )]
)

def run_truthlens_verification(user_input: str, user_id: str = "default_user", session_id: str = "temp_session", api_key: Optional[str] = None) -> Generator[Event, None, None]:
    """Runs the TruthLens multi-agent workflow on the provided user input."""
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        os.environ["GEMINI_API_KEY"] = api_key
        
    session_service = InMemorySessionService()
    runner = Runner(
        agent=truthlens_workflow,
        app_name="TruthLensApp",
        session_service=session_service,
        auto_create_session=True
    )
    
    # Wrap input in Content object for runner
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_input)]
    )
    
    # Yield events to allow real-time console/UI streaming of agent thoughts
    return runner.run(
        user_id=user_id,
        session_id=session_id,
        new_message=content
    )

