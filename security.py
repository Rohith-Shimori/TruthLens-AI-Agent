import re
import time
from typing import Dict, Tuple

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

    def check_rate_limit(self, identifier: str) -> bool:
        """Checks if the request exceeds the rate limit. Returns True if OK, False if rate limited."""
        now = time.time()
        if identifier not in self.request_history:
            self.request_history[identifier] = []
            
        # Clean up old timestamps
        self.request_history[identifier] = [
            ts for ts in self.request_history[identifier] 
            if now - ts < self.rate_limit_window
        ]
        
        if len(self.request_history[identifier]) >= self.max_requests:
            return False
            
        self.request_history[identifier].append(now)
        return True

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
