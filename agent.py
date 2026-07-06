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
    """Adds a brief delay of 0.8 seconds before sending requests to the LLM to prevent concurrent burst rate limits on Gemini Free Tier."""
    node_name = callback_context.node.name if (callback_context and callback_context.node) else "unknown"
    print(f"[TruthLens] Rate spacing: sleeping for 0.8s before calling model in agent '{node_name}'...")
    time.sleep(0.8)
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
        "provided in JSON by the IngestionAgent and isolate the key, verifiable factual claims.\n"
        "Rules:\n"
        "1. Read the input JSON which contains 'input_type', 'title', and 'content'.\n"
        "2. Ignore opinions, feelings, or general comments. Focus only on statements that can be proven true or false.\n"
        "3. Extract up to 3 core claims.\n"
        "4. Your response MUST be a JSON object carrying over the original Ingestion fields ('input_type', 'title', 'content') "
        "and adding a new field 'claims' which is a list of objects. Each claim object must contain: 'id' (integer), "
        "'claim_text' (string), and 'reason' (why it is check-worthy)."
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
        "You are the EvidenceRetrieverAgent of TruthLens. Your role is to verify the claims "
        "contained in the incoming JSON from the ClaimExtractionAgent.\n"
        "Rules:\n"
        "1. Read the input JSON which contains 'input_type', 'title', 'content', and 'claims'.\n"
        "2. For each claim in the 'claims' list, use the 'search_google_grounding' and 'search_wikipedia' tools to look up facts.\n"
        "3. Collect the best evidence, noting URLs and publisher titles.\n"
        "4. Your response MUST be a JSON object carrying over all the fields ('input_type', 'title', 'content', 'claims') "
        "and adding a new field 'evidence' which is a list of objects. Each evidence object must contain: "
        "'claim_id' (integer matching the claim's ID), and 'sources' (a list of objects, each containing: "
        "'title' (publisher/article title), 'url' (direct link), and 'snippet' (supporting/contradicting quote))."
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
        "provided in the incoming JSON from the EvidenceRetrieverAgent.\n"
        "Rules:\n"
        "1. Read the input JSON which contains 'input_type', 'title', 'content', 'claims', and 'evidence'.\n"
        "2. Collect all URLs from the 'evidence' list.\n"
        "3. Use the 'analyze_source_credibility_tool' to get classifications and scores for these domains.\n"
        "4. Your response MUST be a JSON object carrying over all the fields ('input_type', 'title', 'content', 'claims', 'evidence') "
        "and adding a new field 'credibility' which is an object containing: 'overall_score' (number from 0 to 100), "
        "'rating' (e.g. High, Medium, Low), and 'details' (a list of objects, each containing 'domain', 'safety_level', and 'explanation')."
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
        "You are the BiasAnalyzerAgent of TruthLens. Your role is to evaluate the tone, loaded language, and objectivity "
        "of the original content text provided in the incoming JSON.\n"
        "Rules:\n"
        "1. Read the input JSON which contains 'input_type', 'title', 'content', 'claims', 'evidence', and 'credibility'.\n"
        "2. Use the 'analyze_bias_tool' on the 'content' field to get sensation and sentiment scores.\n"
        "3. Perform a qualitative analysis of logical fallacies and political/ideological bias.\n"
        "4. Your response MUST be a JSON object carrying over all the fields ('input_type', 'title', 'content', 'claims', 'evidence', 'credibility') "
        "and adding a new field 'bias' which is an object containing: 'sensationalism_score' (number from 0 to 100), "
        "'fallacies' (a list of strings), and 'analysis_summary' (a brief description of objectivity)."
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
        "ratings from the incoming JSON to determine the veracity of each claim.\n"
        "Rules:\n"
        "1. Read the input JSON which contains 'input_type', 'title', 'content', 'claims', 'evidence', 'credibility', and 'bias'.\n"
        "2. For each claim in the 'claims' list, evaluate all matching items in 'evidence' and 'credibility' to assign a verdict:\n"
        "   - True: Claim is fully supported by credible evidence.\n"
        "   - Mostly True: Claim is accurate in essence, but has minor context gaps.\n"
        "   - Misleading: Claim contains elements of truth but is presented in a way to deceive.\n"
        "   - False: Claim is directly contradicted by reliable evidence.\n"
        "   - Unverified: There is not enough reliable evidence to prove or disprove the claim.\n"
        "3. Calculate an overall confidence score (0 to 100) based on source reliability and evidence match.\n"
        "4. Your response MUST be a JSON object carrying over all the fields ('input_type', 'title', 'content', 'claims', 'evidence', 'credibility', 'bias') "
        "and adding a new field 'verdicts' which is a list of objects (each containing 'claim_id', 'verdict', and 'rationale') "
        "and a field 'overall_confidence' (number from 0 to 100)."
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
        "You are the ReportGeneratorAgent of TruthLens. Your role is to synthesize the findings from the VerdictAgent "
        "contained in the incoming JSON and write a beautiful, comprehensive, and objective markdown report for the user.\n"
        "Rules:\n"
        "1. Read the input JSON which contains 'input_type', 'title', 'content', 'claims', 'evidence', 'credibility', 'bias', 'verdicts', and 'overall_confidence'.\n"
        "2. Do not complain about missing details. All details are fully provided in the input JSON structure. Parse it and write a report.\n"
        "3. The report MUST follow this layout:\n"
        "   - Title: # 🛡️ TruthLens Fact-Check Report\n"
        "   - Verdict Banner: A glowing container or large header displaying the overall verdict of the primary claim, the confidence score percentage, and an emoji.\n"
        "   - Executive Summary: A concise, 2-3 sentence overview of what the claim is and the result of the investigation.\n"
        "   - Claims & Evidence Breakdown: For each claim, list the claim, its verdict, and the supporting evidence with direct source titles and URLs (format as clickable markdown links like [Reuters](url)).\n"
        "   - Source Credibility Assessment: Summarize the credibility of the sources, listing trusted and untrusted links with score.\n"
        "   - Bias & Sensationalism Analysis: Detail the sensationalism score, emotional loading, and logical fallacies.\n"
        "   - Digital Literacy Guidance: Provide actionable advice on how to spot this specific type of misinformation.\n"
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

