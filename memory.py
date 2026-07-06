import sqlite3
import hashlib
import json
import time
from typing import Optional, Dict, Any, List
from config import DB_PATH

class MemoryManager:
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database and creates the schema if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
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
        """Returns MD5 hash of text for quick lookup."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def check_cache(self, text: str) -> Optional[Dict[str, Any]]:
        """Checks if a similar verification already exists in the cache."""
        h = self._get_hash(text)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM verification_cache WHERE content_hash = ?", 
            (h,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # Convert SQLite row back to dictionary and parse JSON fields
            data = dict(row)
            try:
                data['claims'] = json.loads(data['claims'])
                data['evidence'] = json.loads(data['evidence'])
                data['bias_analysis'] = json.loads(data['bias_analysis'])
                data['credibility_analysis'] = json.loads(data['credibility_analysis'])
                return data
            except json.JSONDecodeError:
                # If JSON parsing fails, cache might be corrupted, so return None
                return None
        return None

    def save_cache(self, text: str, input_type: str, result: Dict[str, Any]):
        """Saves a verification result to the cache."""
        h = self._get_hash(text)
        conn = sqlite3.connect(self.db_path)
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
            print(f"Error saving to database cache: {e}")
        finally:
            conn.close()

    def get_recent_verifications(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent verification items from cache for history visualization."""
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
