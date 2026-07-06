import urllib.parse
from typing import Dict, Any, List
from config import RELIABLE_DOMAINS, UNRELIABLE_DOMAINS, CREDIBILITY_MULTIPLIERS

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
