import os
import re
import time
import sqlite3
import hashlib
import json
import logging
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger("TruthLens.Utils")

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "cache" / "truthlens.db"

# Cache TTL (Time-To-Live) in seconds — 7 days
CACHE_TTL = int(os.getenv("CACHE_TTL", str(86400 * 7)))

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
    "satire_parody": 0.05,       # Onion, Babylon Bee
    "known_misinformation": 0.0  # Sites known to publish false claims
}


class SecurityManager:
    def __init__(self, rate_limit_window_secs: int = 60, max_requests_per_window: int = 10):
        self.rate_limit_window = rate_limit_window_secs
        self.max_requests = max_requests_per_window
        # Map of ip/user_identifier -> list of timestamps
        self.request_history: Dict[str, list] = {}
        
        # Patterns commonly used for prompt injection
        self.injection_patterns = [
            re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
            re.compile(r"system\s+(?:override|bypass)", re.IGNORECASE),
            re.compile(r"you\s+are\s+now\s+a\s+different\s+agent", re.IGNORECASE),
            re.compile(r"forget\s+what\s+you\s+were\s+told", re.IGNORECASE),
            re.compile(r"jailbreak", re.IGNORECASE),
            re.compile(r"assistant\s+must\s+now\s+act\s+as", re.IGNORECASE),
            re.compile(r"do\s+not\s+verify\s+anything", re.IGNORECASE),
            re.compile(r"always\s+(?:say|return)\s+(?:true|false)", re.IGNORECASE)
        ]

    def sanitize_input(self, text: str) -> str:
        """Sanitizes text to remove potential HTML tags, scripts, and excessively weird characters."""
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r"<[^>]*>", "", text)
        # Remove script tags or iframe content specifically
        text = re.sub(r"javascript:", "", text, flags=re.IGNORECASE)
        # Trim whitespace
        return text.strip()

    def check_rate_limit(self, identifier: str) -> Dict[str, Any]:
        """Checks if the request exceeds the rate limit. Returns dict with 'allowed' key."""
        now = time.time()
        if identifier not in self.request_history:
            self.request_history[identifier] = []
            
        # Clean up old timestamps
        self.request_history[identifier] = [
            ts for ts in self.request_history[identifier] 
            if now - ts < self.rate_limit_window
        ]
        
        if len(self.request_history[identifier]) >= self.max_requests:
            return {"allowed": False, "reason": "Rate limit exceeded. Please wait."}
            
        self.request_history[identifier].append(now)
        return {"allowed": True}

    def detect_prompt_injection(self, text: str) -> Tuple[bool, str]:
        """Scans input for prompt injection signatures. Returns (is_injection, reason)."""
        if not text:
            return False, ""
            
        for pattern in self.injection_patterns:
            if pattern.search(text):
                return True, f"Input failed security validation: Triggered pattern '{pattern.pattern}'"
        
        # Check for excessive instructions/roleplay cues
        if text.count("Assistant:") > 3 or text.count("System:") > 3 or text.count("User:") > 3:
            return True, "Input contains suspiciously structured conversational prompts."
            
        return False, ""

    def validate_content_length(self, text: str, max_chars: int = 50000) -> bool:
        """Validates that the content is within a reasonable size."""
        return len(text) <= max_chars


class MemoryManager:
    def __init__(self):
        self.db_path = DB_PATH
        # Ensure parent directory of DB_PATH exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database with WAL mode for thread safety."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        # Table for caching full verifications
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_cache (
                content_hash TEXT PRIMARY KEY,
                query_text TEXT,
                input_type TEXT, -- 'text', 'url', 'image'
                verdict TEXT,
                confidence_score REAL,
                claims TEXT, -- JSON array of claims
                evidence TEXT, -- JSON array/object of evidence
                bias_analysis TEXT, -- JSON analysis
                credibility_analysis TEXT, -- JSON analysis
                created_at INTEGER
            )
        """)
        
        # Table for storing individual claims and their evidence for general queries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verified_claims (
                claim_hash TEXT PRIMARY KEY,
                claim_text TEXT,
                verdict TEXT,
                confidence REAL,
                evidence TEXT, -- JSON references
                created_at INTEGER
            )
        """)
        
        conn.commit()
        conn.close()

    def _get_hash(self, text: str) -> str:
        """Returns SHA-256 hash of text for quick lookup."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def check_cache(self, text: str) -> Optional[Dict[str, Any]]:
        """Checks if a similar verification already exists in the cache (with TTL)."""
        h = self._get_hash(text)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM verification_cache WHERE content_hash = ?", 
            (h,)
        )
        row = cursor.fetchone()
        
        if row:
            data = dict(row)
            # Check if cache entry has expired (TTL)
            created_at = data.get('created_at', 0)
            if (int(time.time()) - created_at) > CACHE_TTL:
                # Expired — delete stale entry
                cursor.execute("DELETE FROM verification_cache WHERE content_hash = ?", (h,))
                conn.commit()
                conn.close()
                logger.info(f"Cache entry expired for hash {h[:12]}...")
                return None
            
            try:
                data['claims'] = json.loads(data['claims'])
                data['evidence'] = json.loads(data['evidence'])
                data['bias_analysis'] = json.loads(data['bias_analysis'])
                data['credibility_analysis'] = json.loads(data['credibility_analysis'])
                conn.close()
                return data
            except json.JSONDecodeError:
                conn.close()
                return None
        conn.close()
        return None

    def save_cache(self, text: str, input_type: str, result: Dict[str, Any]):
        """Saves a verification result to the cache."""
        h = self._get_hash(text)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO verification_cache (
                    content_hash, query_text, input_type, verdict, confidence_score,
                    claims, evidence, bias_analysis, credibility_analysis, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                h,
                text,
                input_type,
                result.get("verdict", "Unknown"),
                result.get("confidence_score", 0.0),
                json.dumps(result.get("claims", [])),
                json.dumps(result.get("evidence", [])),
                json.dumps(result.get("bias_analysis", {})),
                json.dumps(result.get("credibility_analysis", {})),
                int(time.time())
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving to database cache: {e}")
        finally:
            conn.close()

    def get_recent_verifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent verification items from cache for history visualization."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT query_text, verdict, confidence_score, created_at FROM verification_cache ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def get_analytics(self) -> Dict[str, Any]:
        """Gathers stats/analytics on stored entries."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM verification_cache")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT verdict, COUNT(*) FROM verification_cache GROUP BY verdict")
        verdict_counts = dict(cursor.fetchall())
        
        cursor.execute("SELECT AVG(confidence_score) FROM verification_cache")
        avg_confidence = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            "total_verifications": total_count,
            "verdict_distribution": verdict_counts,
            "average_confidence": round(avg_confidence, 2)
        }


class CredibilityScorer:
    def __init__(self):
        self.reliable_domains = RELIABLE_DOMAINS
        self.unreliable_domains = UNRELIABLE_DOMAINS
        self.multipliers = CREDIBILITY_MULTIPLIERS

    def extract_domain(self, url: str) -> str:
        """Helper to extract domain name from a URL."""
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def evaluate_source(self, url: str) -> Dict[str, Any]:
        """Evaluates a single URL and returns credibility parameters."""
        domain = self.extract_domain(url)
        if not domain:
            return {
                "domain": "Unknown",
                "score": 40.0,
                "category": "unknown",
                "explanation": "No valid domain name could be extracted from source."
            }

        # Exact match check
        if domain in self.reliable_domains:
            return {
                "domain": domain,
                "score": 95.0,
                "category": "trusted_news",
                "explanation": f"Domain '{domain}' is a verified trustworthy news or fact-checking source."
            }
        
        if domain in self.unreliable_domains:
            return {
                "domain": domain,
                "score": 10.0,
                "category": "known_misinformation",
                "explanation": f"Domain '{domain}' is flagged in our repository as having a history of spreading satire or misinformation."
            }

        # Subdomain / partial check (e.g. en.wikipedia.org matches wikipedia.org)
        for rel in self.reliable_domains:
            if domain.endswith("." + rel) or domain == rel:
                return {
                    "domain": domain,
                    "score": 90.0,
                    "category": "trusted_news",
                    "explanation": f"Domain matches known trusted root domain '{rel}'."
                }

        for unrel in self.unreliable_domains:
            if domain.endswith("." + unrel) or domain == unrel:
                return {
                    "domain": domain,
                    "score": 10.0,
                    "category": "known_misinformation",
                    "explanation": f"Domain matches known unreliable root domain '{unrel}'."
                }

        # Standard heuristics based on suffix/type
        if domain.endswith((".gov", ".mil")):
            return {
                "domain": domain,
                "score": 85.0,
                "category": "official_govt",
                "explanation": "Official government website domain."
            }
        
        if domain.endswith(".edu"):
            return {
                "domain": domain,
                "score": 88.0,
                "category": "academic",
                "explanation": "Educational institution domain."
            }

        # Default classification based on domain heuristics
        social_media_platforms = {"twitter.com", "x.com", "facebook.com", "reddit.com", "t.me", "instagram.com", "tiktok.com", "linkedin.com"}
        if domain in social_media_platforms or any(p in domain for p in social_media_platforms):
            return {
                "domain": domain,
                "score": 30.0,
                "category": "social_media",
                "explanation": "Social media sharing platform. Information is user-generated and highly unverified."
            }

        return {
            "domain": domain,
            "score": 60.0,  # Neutral baseline
            "category": "general_web",
            "explanation": f"Source domain '{domain}' is evaluated under general web heuristics. Baselines apply."
        }

    def aggregate_credibility(self, urls: List[str]) -> Dict[str, Any]:
        """Aggregates credibility across multiple URLs."""
        if not urls:
            return {
                "overall_score": 50.0,
                "rating": "Medium (Unverified)",
                "breakdown": [],
                "reason": "No external source citations were provided or found."
            }

        results = [self.evaluate_source(url) for url in urls]
        scores = [r["score"] for r in results]
        overall_score = sum(scores) / len(scores)

        if overall_score >= 80:
            rating = "High Credibility"
            reason = "Most cited sources are highly reliable, well-established institutions or official fact-checkers."
        elif overall_score >= 50:
            rating = "Medium Credibility"
            reason = "Citations are mix of general news, unverified web sources, or have not been systematically verified."
        else:
            rating = "Low Credibility"
            reason = "A significant portion of reference sources are flagged as unreliable or belong to user-generated social media networks."

        return {
            "overall_score": round(overall_score, 1),
            "rating": rating,
            "breakdown": results,
            "reason": reason
        }


class BiasAnalyzer:
    def __init__(self):
        # Single-word sensational terms
        self.sensational_single_words = {
            "shocking", "exposed", "destroy", "scandal", "conspiracy", "secret", 
            "unbelievable", "miracle", "furious", "slams", "blasts", 
            "epic", "insane", "hiding", "revealed",
            "horrific", "tragedy", "miraculous", "plot", "cabal"
        }
        
        # Multi-word sensational phrases
        self.sensational_phrases = {
            "must read", "mind-blowing", "truth about", "cover-up", "cover up"
        }

    def calculate_sensationalism_score(self, text: str) -> float:
        """Heuristically calculates sensationalism score based on word matching, phrases, and punctuation."""
        if not text:
            return 0.0
            
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        if not words:
            return 0.0
            
        # Count single-word matches
        match_count = sum(1 for w in words if w in self.sensational_single_words)
        
        # Count multi-word phrase matches
        phrase_count = sum(1 for phrase in self.sensational_phrases if phrase in text_lower)
        
        # Check punctuation alerts (excessive exclamation or question marks)
        exclamations = len(re.findall(r'!{2,}', text))
        question_marks = len(re.findall(r'\?{2,}', text))
        all_caps_words = sum(1 for w in re.findall(r'\b[A-Z]{4,}\b', text))
        
        # Scoring scale (0 - 100)
        total_matches = match_count + phrase_count
        base_score = (total_matches / max(len(words), 1)) * 500  # scaled more reasonably
        punct_bonus = (exclamations * 10) + (question_marks * 5) + (all_caps_words * 4)
        
        final_score = min(base_score + punct_bonus, 100.0)
        return round(final_score, 1)

    def analyze_bias_local(self, text: str) -> Dict[str, Any]:
        """Performs localized heuristic analysis of sentiment and sensationalism."""
        sensationalism = self.calculate_sensationalism_score(text)
        
        # Basic text structure features
        all_caps_count = len(re.findall(r'\b[A-Z]{4,}\b', text))
        exclamation_count = text.count("!")
        
        # Determine rating
        if sensationalism > 60:
            rating = "Extremely Sensationalist"
            verdict = "High emotional framing; typical of clickbait or inflammatory posts."
        elif sensationalism > 30:
            rating = "Moderately Sensationalist"
            verdict = "Uses descriptive, loaded language to drive engagement."
        else:
            rating = "Objective / Neutral"
            verdict = "Language matches objective reporting guidelines."

        return {
            "sensationalism_score": sensationalism,
            "sensationalism_rating": rating,
            "heuristic_verdict": verdict,
            "metrics": {
                "all_caps_words": all_caps_count,
                "exclamations": exclamation_count
            }
        }
