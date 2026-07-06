import json
from fastmcp import FastMCP
from tools import search_google_grounding, search_wikipedia
from credibility import CredibilityScorer
from bias_analyzer import BiasAnalyzer

# Initialize FastMCP server
mcp = FastMCP("TruthLens Verification Server")

# Initialize helpers
cred_scorer = CredibilityScorer()
bias_anal = BiasAnalyzer()

@mcp.tool()
def search_evidence(query: str) -> str:
    """
    Searches multiple sources (Wikipedia and Google Grounded Search) for evidence regarding a claim.
    Returns a unified JSON string of results.
    """
    if not query:
        return json.dumps({"error": "Empty search query"})
        
    print(f"[MCP] Searching evidence for: {query}")
    
    # 1. Wiki Search
    wiki_results = search_wikipedia(query)
    
    # 2. Google Search Grounding
    google_results = search_google_grounding(query)
    
    combined = {
        "query": query,
        "wikipedia_results": wiki_results,
        "web_results": google_results
    }
    
    return json.dumps(combined, indent=2)

@mcp.tool()
def check_source_credibility(url: str) -> str:
    """
    Evaluates the credibility and reliability of a given news source URL.
    Returns a JSON string containing the domain rating and breakdown.
    """
    if not url:
        return json.dumps({"error": "Empty URL"})
        
    print(f"[MCP] Checking credibility for URL: {url}")
    res = cred_scorer.evaluate_source(url)
    return json.dumps(res, indent=2)

@mcp.tool()
def analyze_bias(text: str) -> str:
    """
    Analyzes input text for sensationalism, loaded language, and potential bias indicators.
    Returns a JSON string containing the scores and indicators.
    """
    if not text:
        return json.dumps({"error": "Empty text content"})
        
    print(f"[MCP] Analyzing bias in text")
    res = bias_anal.analyze_bias_local(text)
    return json.dumps(res, indent=2)

if __name__ == "__main__":
    # Start the MCP server using stdio transport (suitable for local host integration)
    mcp.run()
