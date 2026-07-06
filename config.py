import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "truthlens.db"

# API Configurations
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    # Look for GEMINI_API_KEY as a fallback
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# Model Configuration
DEFAULT_MODEL = "gemini-2.5-flash"

# Curated lists for source credibility
RELIABLE_DOMAINS = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com", 
    "washingtonpost.com", "bloomberg.com", "npr.org", "theguardian.com", 
    "nature.com", "science.org", "wikipedia.org", "factcheck.org", 
    "snopes.com", "politifact.com", "reuters.com/fact-check"
}

UNRELIABLE_DOMAINS = {
    "infowars.com", "naturalnews.com", "breitbart.com", "gatewaypundit.com",
    "dailywire.com", "rt.com", "sputniknews.com", "theonion.com", "babylonbee.com",
    "worldnewsdailyreport.com", "clickhole.com", "politicalgarbagechute.com",
    "huzlers.com", "nationalreport.net", "empirenews.net", "abclocal.go.com.co"
}

# Source category multipliers
CREDIBILITY_MULTIPLIERS = {
    "official_factcheck": 1.0,   # Snopes, Politifact, etc.
    "trusted_news": 0.9,         # Reuters, AP, BBC
    "academic": 0.95,            # Nature, Science, universities
    "general_news": 0.7,         # Standard commercial news outlets
    "social_media": 0.2,         # Twitter, Reddit, Facebook posts (unverified)
    "blog_forum": 0.3,           # Medium, Substack, forums (unless trusted author)
    " satire_parody": 0.05,       # Onion, Babylon Bee
    "known_misinformation": 0.0  # Sites known to publish false claims
}
