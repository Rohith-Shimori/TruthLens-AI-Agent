import re
from typing import Dict, Any, List

class BiasAnalyzer:
    def __init__(self):
        # Sensationalism and emotional words common in clickbait/fake news
        self.sensational_words = {
            "shocking", "exposed", "destroy", "scandal", "conspiracy", "secret", 
            "unbelievable", "must read", "miracle", "furious", "slams", "blasts", 
            "epic", "mind-blowing", "insane", "hiding", "truth about", "revealed",
            "horrific", "tragedy", "miraculous", "plot", "cover-up", "cabal"
        }
        
        self.logical_fallacies = {
            "ad_hominem": "Attacking the person rather than the argument.",
            "strawman": "Misrepresenting an opponent's position to make it easier to attack.",
            "false_dichotomy": "Presenting only two options when more exist.",
            "appeal_to_emotion": "Manipulating emotions to win an argument rather than using facts.",
            "slippery_slope": "Asserting that a relatively small step will inevitably lead to a chain of negative events.",
            "hasty_generalization": "Drawing a conclusion based on a small or non-representative sample."
        }

    def calculate_sensationalism_score(self, text: str) -> float:
        """Heuristically calculates sensationalism score based on word matching and punctuation."""
        if not text:
            return 0.0
            
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return 0.0
            
        # Count matchings
        match_count = sum(1 for w in words if w in self.sensational_words)
        
        # Check punctuation alerts (excessive exclamation or question marks)
        exclamations = len(re.findall(r'!{2,}', text))
        question_marks = len(re.findall(r'\?{2,}', text))
        all_caps_words = sum(1 for w in re.findall(r'\b[A-Z]{4,}\b', text))
        
        # Scoring scale (0 - 100)
        base_score = (match_count / len(words)) * 1000  # scaled
        punct_bonus = (exclamations * 10) + (question_marks * 5) + (all_caps_words * 4)
        
        final_score = min(base_score + punct_bonus, 100.0)
        return round(final_score, 1)

    def analyze_bias_local(self, text: str) -> Dict[str, Any]:
        """Performs localized heuristic analysis of sentiment and sensationalism."""
        sensationalism = self.calculate_sensationalism_score(text)
        
        # Basic text structure features
        all_caps_count = len(re.findall(r'\b[A-Z]{3,}\b', text))
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
