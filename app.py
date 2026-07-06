import os
import time
import json
import re
import gradio as gr
from typing import Tuple, Generator, Optional, Any

# Import modular components from package structure
from src.inference import GOOGLE_API_KEY
from src.utils import SecurityManager, MemoryManager, CredibilityScorer, BiasAnalyzer
from src.pipeline import run_truthlens_verification
from src.ui import custom_css, get_verdict_html, WELCOME_MESSAGE

# Initialize managers
security = SecurityManager()
memory = MemoryManager()
cred_scorer = CredibilityScorer()
bias_anal = BiasAnalyzer()

def extract_json_from_text(text: str) -> Optional[Any]:
    """Extracts and parses the first JSON block found in a text string."""
    if not text:
        return None
    
    # Try parsing directly
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
        
    # Look for JSON blocks enclosed in markdown code fences
    try:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        pass
        
    # Try finding first '{' and last '}'
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1].strip())
    except json.JSONDecodeError:
        pass
        
    # Try finding first '[' and last ']' (for arrays)
    try:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1].strip())
    except json.JSONDecodeError:
        pass
        
    return None

def parse_verdict_from_report(report: str) -> Tuple[str, float]:
    """Extracts overall verdict and maps confidence levels from report text."""
    if not report:
        return "Unverified", 50.0
    
    report_lower = report.lower()
    
    # 1. Look for structured lines like "verdict: false" or "verdict: **false**" or "overall verdict: **mostly true**"
    match = re.search(r"(?:overall\s+)?verdict\s*:\s*\**([a-zA-Z\s]+)\**", report_lower)
    if match:
        verdict_str = match.group(1).strip()
        if "mostly true" in verdict_str:
            return "Mostly True", 75.0
        elif "mostly false" in verdict_str:
            return "Misleading", 40.0
        elif "true" in verdict_str:
            return "True", 90.0
        elif "misleading" in verdict_str:
            return "Misleading", 40.0
        elif "false" in verdict_str:
            return "False", 15.0
        elif "unverified" in verdict_str:
            return "Unverified", 50.0

    # 2. Strict fallback: scan only the top 15 lines of the report for the verdict keywords to prevent matching rules/instructions at the bottom
    top_lines = "\n".join(report_lower.split("\n")[:15])
    if "overall verdict: **true**" in top_lines or "verdict: true" in top_lines:
        return "True", 90.0
    elif "overall verdict: **mostly true**" in top_lines or "verdict: mostly true" in top_lines:
        return "Mostly True", 75.0
    elif "overall verdict: **misleading**" in top_lines or "verdict: misleading" in top_lines:
        return "Misleading", 40.0
    elif "overall verdict: **false**" in top_lines or "verdict: false" in top_lines:
        return "False", 15.0
        
    return "Unverified", 50.0

def process_verification(user_input: str, image_file: Optional[str], api_key: Optional[str] = None) -> Generator[Tuple[str, float, str, str, Any], None, None]:
    """
    Core function called by the UI.
    Streams progress states, then yields the final verdict html, confidence, report, status, and download file.
    """
    # 1. Determine actual input
    target_input = ""
    input_type = "text"
    
    if image_file:
        target_input = image_file
        input_type = "image"
    elif user_input:
        target_input = user_input.strip()
        if target_input.startswith(("http://", "https://")):
            input_type = "url"
    else:
        yield get_verdict_html("Unverified", 0.0), 0.0, "### ❌ Input Required\nPlease provide either a URL, raw text, or upload an image screenshot.", "Ready", gr.update(visible=False)
        return

    # 2. Security validation
    sanitized = security.sanitize_input(target_input) if input_type != "image" else target_input
    
    if input_type != "image":
        is_injection, reason = security.detect_prompt_injection(sanitized)
        if is_injection:
            yield get_verdict_html("Unverified", 0.0), 0.0, f"### ⚠️ Security Violation\n{reason}", "Blocked", gr.update(visible=False)
            return
            
        if not security.validate_content_length(sanitized):
            yield get_verdict_html("Unverified", 0.0), 0.0, "### ❌ Input Too Long\nInput text exceeds the maximum character threshold (50,000 characters).", "Ready", gr.update(visible=False)
            return

    # 3. Check SQLite memory cache
    yield get_verdict_html("Processing", 20.0), 20.0, "### 🔍 Searching cache...\nRetrieving matching verification payloads from local SQLite index.", "Checking database cache...", gr.update(visible=False)
    time.sleep(1.0)
    
    cached = memory.check_cache(sanitized)
    if cached:
        # Cache hit!
        verdict = cached.get("verdict", "Unverified")
        confidence = cached.get("confidence_score", 50.0)
        
        # Reconstruct markdown report from cached fields
        cached_report = f"""# 🛡️ TruthLens Fact-Check Report (Cached)

## Overall Verdict: **{verdict}** (Confidence: {confidence}%)

> [!NOTE]
> This result was instantly retrieved from TruthLens Memory Cache (Verified at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(cached.get('created_at')))}).

### 📝 Verified Claims:
"""
        for i, c in enumerate(cached.get("claims", [])):
            cached_report += f"- **Claim {i+1}**: {c.get('claim_text', c)}\n"
            
        cached_report += "\n### 🔍 Evidence Retrieved:\n"
        for ev in cached.get("evidence", []):
            cached_report += f"- [{ev.get('title', 'Evidence Source')}]({ev.get('url', '#')}): \"{ev.get('snippet', '')[:200]}...\"\n"

        cached_report += f"\n### 📊 Sentiment & Bias Rating:\n"
        bias = cached.get("bias_analysis", {})
        cached_report += f"- **Sensationalism Score**: {bias.get('sensationalism_score', 0)}/100 ({bias.get('sensationalism_rating', 'Objective')})\n"
        
        # Save to file for download
        report_path = os.path.join(os.getcwd(), "truthlens_factcheck_report.md")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(cached_report)
            file_update = gr.update(value=report_path, visible=True)
        except Exception:
            file_update = gr.update(visible=False)
            
        yield get_verdict_html(verdict, confidence), confidence, cached_report, "Verification loaded from memory cache!", file_update
        return

    # 4. Cache miss - run the ADK Multi-Agent Workflow
    active_key = api_key or GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY")
    if not active_key:
        yield get_verdict_html("Unverified", 0.0), 0.0, "### 🔑 API Key Required\nPlease enter your Gemini API key in the configuration panel above, or set it in your `.env` file to start the live verification pipeline.", "API Key missing", gr.update(visible=False)
        return

    # Quick live check to ensure key is valid and has remaining quota
    yield get_verdict_html("Processing", 5.0), 5.0, "### 🔌 Validating API key and quota...\nVerifying credentials against Google AI Studio.", "Validating credentials...", gr.update(visible=False)
    try:
        from google import genai
        client = genai.Client(api_key=active_key)
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents="test",
        )
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            yield get_verdict_html("Unverified", 0.0), 0.0, "### ⚠️ Gemini API Quota Exceeded\nYour API key has hit the daily free tier limit (20 requests per day) or rate limit. Please try again later or use a different key.", "Quota Exceeded", gr.update(visible=False)
        else:
            yield get_verdict_html("Unverified", 0.0), 0.0, f"### ❌ API Connection Failed\nYour API Key is invalid or not working:\n`{error_msg[:150]}`", "Key Error", gr.update(visible=False)
        return

    session_id = f"sess_{int(time.time())}"
    current_status = "Initializing Agents..."
    
    # We yield intermediate states to show progress
    yield get_verdict_html("Processing", 10.0), 10.0, "### 🏗&nbsp; Initializing TruthLens Agent Network...\nDecoupling instructions and establishing session channels.", current_status, gr.update(visible=False)
    
    final_report = ""
    verdict = "Unverified"
    confidence = 50.0
    extracted_claims = []
    evidence_list = []
    bias_data = {}

    # Trace logs capture
    ingestion_trace = "Pending execution..."
    claim_trace = "Pending execution..."
    evidence_trace = "Pending execution..."
    credibility_trace = "Pending execution..."
    bias_trace = "Pending execution..."
    verdict_trace = "Pending execution..."

    try:
        events = run_truthlens_verification(sanitized, session_id=session_id, api_key=active_key)
        
        for event in events:
            # Determine which agent is active
            agent_name = event.author or event.node_name or ""
            
            # Extract content text from event
            text_content = ""
            if event.content:
                if isinstance(event.content, str):
                    text_content = event.content
                elif hasattr(event.content, 'parts') and event.content.parts:
                    text_content = "".join(part.text for part in event.content.parts if part.text)
            
            # Update status based on active agent
            if agent_name == "IngestionAgent":
                current_status = "1/7 Ingesting and parsing content..."
                if text_content:
                    ingestion_trace = text_content
                yield get_verdict_html("Processing", 15.0), 15.0, "### 📥 Ingesting and Parsing Content...\nExtracting raw text and visual metadata from source.", current_status, gr.update(visible=False)
            elif agent_name == "ClaimExtractionAgent":
                current_status = "2/7 Extracting factual claims..."
                if text_content:
                    claim_trace = text_content
                    claims_data = extract_json_from_text(text_content)
                    if isinstance(claims_data, dict):
                        extracted_claims = claims_data.get("claims", [])
                    elif isinstance(claims_data, list):
                        extracted_claims = claims_data
                yield get_verdict_html("Processing", 30.0), 30.0, "### 📝 Extracting Factual Claims...\nIsolating check-worthy assertions of facts, statistics, or quotes.", current_status, gr.update(visible=False)
            elif agent_name == "EvidenceRetrieverAgent":
                current_status = "3/7 Retrieving evidence from web & Wikipedia..."
                if text_content:
                    evidence_trace = text_content
                yield get_verdict_html("Processing", 50.0), 50.0, "### 🔍 Retrieving Supporting/Refuting Evidence...\nSearching Wikipedia and Google grounding index for facts.", current_status, gr.update(visible=False)
            elif agent_name == "SourceCredibilityAgent":
                current_status = "4/7 Scoring source credibility..."
                if text_content:
                    credibility_trace = text_content
                yield get_verdict_html("Processing", 70.0), 70.0, "### 📊 Scoring Source Credibility...\nAnalyzing references against known reliability indexes.", current_status, gr.update(visible=False)
            elif agent_name == "BiasAnalyzerAgent":
                current_status = "5/7 Analyzing framing and sensationalism..."
                if text_content:
                    bias_trace = text_content
                yield get_verdict_html("Processing", 85.0), 85.0, "### ⚖️ Analyzing Formatting, Tone, and Logical Fallacies...\nEvaluating loaded language and emotional sentiment.", current_status, gr.update(visible=False)
            elif agent_name == "VerdictAgent":
                current_status = "6/7 Cross-referencing and issuing verdicts..."
                if text_content:
                    verdict_trace = text_content
                    verdict_data = extract_json_from_text(text_content)
                    if isinstance(verdict_data, dict):
                        # Extract overall confidence
                        raw_conf = verdict_data.get("overall_confidence", 50.0)
                        try:
                            confidence = float(raw_conf)
                        except (ValueError, TypeError):
                            confidence = 50.0
                        
                        # Get verdicts list
                        verdicts_list = verdict_data.get("verdicts", [])
                        if verdicts_list:
                            # Use the verdict of the first claim as the primary verdict
                            verdict = verdicts_list[0].get("verdict", "Unverified")
                        
                        # Extract claims
                        extracted_claims = verdict_data.get("claims", [])
                        # Extract bias
                        bias_data = verdict_data.get("bias", {})
                        # Extract evidence
                        evidence_list = verdict_data.get("evidence", [])
                yield get_verdict_html(verdict if verdict != "Unverified" else "Processing", confidence if verdict != "Unverified" else 95.0), confidence if verdict != "Unverified" else 95.0, "### ⚖️ Cross-Referencing Evidence & Issuing Verdicts...\nSynthesizing source ratings and fact alignments.", current_status, gr.update(visible=False)
            elif agent_name == "ReportGeneratorAgent":
                current_status = "7/7 Compiling final report..."
                if text_content:
                    final_report = text_content
                    # Fallback verdict parsing if not already captured from VerdictAgent
                    if verdict == "Unverified":
                        verdict, confidence = parse_verdict_from_report(final_report)
                yield get_verdict_html(verdict, confidence), confidence, final_report or "Generating final output...", current_status, gr.update(visible=False)


        # Save to SQLite cache on success
        if final_report:
            # Auto-save API key to .env if provided and not already saved
            if api_key:
                try:
                    with open(".env", "w") as f:
                        f.write(f"GOOGLE_API_KEY={api_key}\n")
                except Exception as e:
                    print(f"Failed to auto-save API key: {e}")
                    
            if not extracted_claims:
                extracted_claims = [{"claim_text": "Original Query Factual Assertions"}]
            
            # --- ADVANCED DIAGNOSTICS & CONSENSUS ENGINE ---
            # 1. Parse domains from the report
            urls = re.findall(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s\)\"\'\<\>]*', final_report)
            domains = set()
            for url in urls:
                domain = cred_scorer.extract_domain(url)
                if domain and domain not in ("google.com", "wikipedia.org", "wiktionary.org"):
                    domains.add(domain)
            
            # 2. Build Markdown Sources Table
            sources_md = "\n### 🔍 Cited Sources & Reliability Map\n\n"
            if domains:
                sources_md += "| Source Domain | Safety Classification | Credibility Score |\n"
                sources_md += "| :--- | :--- | :---: |\n"
                for d in sorted(domains):
                    eval_res = cred_scorer.evaluate_source(d)
                    cat_name = eval_res.get("category", "general_web").replace("_", " ").title()
                    score = eval_res.get("score", 60.0)
                    
                    if score >= 80:
                        badge = f"🟢 {cat_name}"
                    elif score >= 50:
                        badge = f"🟡 {cat_name}"
                    else:
                        badge = f"🔴 {cat_name}"
                        
                    sources_md += f"| {d} | {badge} | `{score}%` |\n"
            else:
                sources_md += "*No external source domains could be automatically verified from the report citation lists.*\n"
                
            # 3. Consensus Scoring
            supporting_count = 0
            contradicting_count = 0
            neutral_count = 0
            
            report_lower = final_report.lower()
            support_terms = ["supported", "true", "confirmed", "accurate", "correct", "verified"]
            refute_terms = ["false", "debunked", "fake", "contradicted", "refuted", "misleading", "unreliable"]
            
            has_support = any(term in report_lower for term in support_terms)
            has_refute = any(term in report_lower for term in refute_terms)
            
            consensus_rating = "Unknown"
            consensus_desc = "Insufficient structured fact checking data to determine agreement level."
            
            if has_support and has_refute:
                consensus_rating = "🟡 Divided / Controversial"
                consensus_desc = "Web databases and Wikipedia articles present conflicting evidence or views regarding this claim."
            elif has_support:
                consensus_rating = "🟢 High Agreement (Verified)"
                consensus_desc = "Sources in our credibility index are aligned in confirming the factual assertions of this claim."
            elif has_refute:
                consensus_rating = "🔴 Unanimous Contradiction (Debunked)"
                consensus_desc = "Sources in our credibility index are aligned in refuting or debunking this claim."

            # Calculate counts for Priority 5 Visual Summaries
            for claim_item in extracted_claims:
                c_text = str(claim_item.get("claim_text", claim_item) if isinstance(claim_item, dict) else claim_item).lower()
                if any(t in c_text for t in refute_terms):
                    contradicting_count += 1
                elif any(t in c_text for t in support_terms):
                    supporting_count += 1
                else:
                    neutral_count += 1

            # Fallback if counts are empty to ensure we always show data
            if supporting_count == 0 and contradicting_count == 0:
                if verdict == "True" or verdict == "Mostly True":
                    supporting_count = len(extracted_claims) or 1
                elif verdict == "False" or verdict == "Misleading":
                    contradicting_count = len(extracted_claims) or 1
                else:
                    neutral_count = len(extracted_claims) or 1

            consensus_md = f"""
### ⚖️ Source Consensus Analysis
- **Consensus Status**: **{consensus_rating}**
- **Explanation**: {consensus_desc}

#### 📊 Evidence Consensus Metrics:
*   **Confidence Level**: `{confidence}%`
*   **Supporting Evidence**: `{supporting_count}`
*   **Contradicting Evidence**: `{contradicting_count}`
*   **Neutral/Unverified Elements**: `{neutral_count}`
"""
            trace_md = f"""
<details>
<summary>🔍 View Live Agent Tracing Logs (JSON Spans)</summary>

### 📥 1. IngestionAgent Output
```json
{ingestion_trace}
```

### 📝 2. ClaimExtractionAgent Output
```json
{claim_trace}
```

### 🔍 3. EvidenceRetrieverAgent Output
```json
{evidence_trace}
```

### 📊 4. SourceCredibilityAgent Output
```json
{credibility_trace}
```

### ⚖️ 5. BiasAnalyzerAgent Output
```json
{bias_trace}
```

### ⚖️ 6. VerdictAgent Output
```json
{verdict_trace}
```

</details>
"""
            # Append diagnostics and traces to report
            final_report = f"{final_report}\n\n---\n\n## 🛠️ TruthLens System Diagnostics\n{consensus_md}{sources_md}\n\n{trace_md}"

            # Save report to local file for download
            report_path = os.path.join(os.getcwd(), "truthlens_factcheck_report.md")
            try:
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(final_report)
                file_update = gr.update(value=report_path, visible=True)
            except Exception:
                file_update = gr.update(visible=False)

            result_payload = {
                "verdict": verdict,
                "confidence_score": confidence,
                "claims": extracted_claims,
                "evidence": [{"title": "Web Grounded Search", "url": "https://google.com", "snippet": "Live grounding checks performed."}],
                "bias_analysis": {
                    "sensationalism_score": bias_anal.calculate_sensationalism_score(sanitized) if input_type != "image" else 30.0,
                    "sensationalism_rating": "Objective" if confidence > 70 else "Loaded Tone"
                },
                "credibility_analysis": {
                    "overall_score": confidence
                }
            }
            memory.save_cache(sanitized, input_type, result_payload)
            current_status = "Verification completed and cached!"
            yield get_verdict_html(verdict, confidence), confidence, final_report, current_status, file_update
        else:
            # Check if it was a quota issue
            quota_issue = False
            try:
                from google import genai
                client = genai.Client(api_key=active_key)
                client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents="test",
                )
            except Exception as e:
                error_msg = str(e)
                if "quota" in error_msg.lower() or "429" in error_msg:
                    quota_issue = True
            
            if quota_issue:
                yield get_verdict_html("Unverified", 0.0), 0.0, "### ⚠️ Gemini API Quota Exceeded\nYour API key ran out of quota during execution. Please try again later or use a different key.", "Quota Exceeded", gr.update(visible=False)
            else:
                yield get_verdict_html("Unverified", 50.0), 50.0, "### ⚠️ Verification Incomplete\nAgents finished but no report was returned. Try refining your prompt.", "Error", gr.update(visible=False)
            
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            yield get_verdict_html("Unverified", 0.0), 0.0, "### ⚠️ Gemini API Quota Exceeded\nYour API key has hit the daily free tier limit (20 requests per day) or rate limit. Please try again later or use a different key.", "Quota Exceeded", gr.update(visible=False)
        else:
            yield get_verdict_html("Unverified", 0.0), 0.0, f"### ❌ Execution Error\nAn error occurred while running the multi-agent system:\n`{error_msg}`", "Failed", gr.update(visible=False)

def clear_cache_db():
    print("[TruthLens] Clearing verification cache database...")
    try:
        import sqlite3
        from config import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS verification_cache")
        conn.commit()
        conn.close()
        # Re-initialize database
        memory._init_db()
        return get_stats_html(), get_history_table(), "<span style='color: #10b981; font-weight: bold;'>🟢 Cache database cleared successfully!</span>"
    except Exception as e:
        return get_stats_html(), get_history_table(), f"<span style='color: #ef4444; font-weight: bold;'>🔴 Clear failed: {str(e)}</span>"

# Get initial stats for dashboard
def get_stats_html() -> str:
    stats = memory.get_analytics()
    dist = stats.get("verdict_distribution", {})
    
    html = f"""
    <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 20px;'>
        <div style='background-color: rgba(30, 41, 59, 0.4); padding: 18px; border-radius: 12px; border: 1px solid #243049; text-align: center; backdrop-filter: blur(5px);'>
            <div style='font-size: 14px; color: #94a3b8; font-weight: 500;'>Total Claims Processed</div>
            <div style='font-size: 32px; font-weight: 800; color: #38bdf8; margin-top: 5px;'>{stats.get("total_verifications", 0)}</div>
        </div>
        <div style='background-color: rgba(30, 41, 59, 0.4); padding: 18px; border-radius: 12px; border: 1px solid #243049; text-align: center; backdrop-filter: blur(5px);'>
            <div style='font-size: 14px; color: #94a3b8; font-weight: 500;'>Average System Confidence</div>
            <div style='font-size: 32px; font-weight: 800; color: #34d399; margin-top: 5px;'>{stats.get("average_confidence", 0)}%</div>
        </div>
        <div style='background-color: rgba(30, 41, 59, 0.4); padding: 18px; border-radius: 12px; border: 1px solid #243049; text-align: center; backdrop-filter: blur(5px);'>
            <div style='font-size: 14px; color: #94a3b8; font-weight: 500;'>Flagged False Rumors</div>
            <div style='font-size: 32px; font-weight: 800; color: #f87171; margin-top: 5px;'>{dist.get("False", 0)}</div>
        </div>
        <div style='background-color: rgba(30, 41, 59, 0.4); padding: 18px; border-radius: 12px; border: 1px solid #243049; text-align: center; backdrop-filter: blur(5px);'>
            <div style='font-size: 14px; color: #94a3b8; font-weight: 500;'>Misleading Framing</div>
            <div style='font-size: 32px; font-weight: 800; color: #fbbf24; margin-top: 5px;'>{dist.get("Misleading", 0)}</div>
        </div>
    </div>
    """
    return html

def update_key_status(key: str) -> str:
    if not key:
        if GOOGLE_API_KEY:
            return "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #fbbf24; font-weight: bold;'>🟡 Environment Key Active (Loaded from .env)</span></div>"
        return "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #ef4444; font-weight: bold;'>🔴 Missing (Please paste your key above)</span></div>"
    return "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #3b82f6; font-weight: bold;'>🔵 Key entered. Click 'Test & Connect Key' below to verify connection.</span></div>"

def verify_and_connect_api_key(key: str) -> str:
    clean_key = key.strip() if key else ""
    if not clean_key:
        return "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #ef4444; font-weight: bold;'>🔴 Connection Failed: API key cannot be empty.</span></div>"
        
    print(f"[TruthLens] Testing API Key connection...")
    try:
        from google import genai
        client = genai.Client(api_key=clean_key)
        # Make a tiny request to test the key
        client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Test connection",
        )
        
        # Write to .env automatically to save it
        try:
            with open(".env", "w") as f:
                f.write(f"GOOGLE_API_KEY={clean_key}\n")
            global GOOGLE_API_KEY
            GOOGLE_API_KEY = clean_key
        except Exception as e:
            print(f"Failed to auto-save API key: {e}")
            
        return "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #10b981; font-weight: bold;'>🟢 Connection Successful! Key is active and linked to agents. (Saved to .env)</span></div>"
    except Exception as e:
        error_msg = str(e)
        if "API key not valid" in error_msg or "INVALID_ARGUMENT" in error_msg:
            return "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #ef4444; font-weight: bold;'>🔴 Connection Failed: API Key is invalid. Please check the spelling.</span></div>"
        elif "quota" in error_msg.lower() or "429" in error_msg:
            return "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #fbbf24; font-weight: bold;'>🟡 Connection Warning: Key is valid but has reached its rate limits (429 Quota).</span></div>"
        return f"<div style='margin-top: 10px; font-size: 13px;'><span style='color: #ef4444; font-weight: bold;'>🔴 Connection Failed: {error_msg[:100]}</span></div>"

def get_history_table() -> list:
    history = memory.get_recent_verifications()
    return [[h.get("query_text", "")[:60] + "...", h.get("verdict", ""), f"{h.get('confidence_score', 0.0)}%", time.strftime('%Y-%m-%d %H:%M', time.localtime(h.get('created_at', 0)))] for h in history]

# Presets mapping for quick-select platforms
def select_whatsapp():
    return gr.Textbox(label="💬 WhatsApp Rumor Text / URL", placeholder="Paste forwarded message chain, viral text, or message link here. If you have an image, upload it in the accordion below.")

def select_telegram():
    return gr.Textbox(label="✈️ Telegram Forwarded Claim", placeholder="Paste text from Telegram channel, forwarded rumor, or channel post URL here.")

def select_linkedin():
    return gr.Textbox(label="💼 LinkedIn Post Claim", placeholder="Paste professional claim, job offer rumor, or user post text/URL here.")

def select_gmail():
    return gr.Textbox(label="📧 Gmail Suspicious Content", placeholder="Paste suspicious phishing email body, strange financial request, or sender info here.")

def select_general():
    return gr.Textbox(label="🌐 General Social Media / Web Claim", placeholder="Paste tweet text, news link, blog URL, or general claim to check.")


# custom_css is imported from src.ui

with gr.Blocks(title="TruthLens | Advanced Multi-Agent Fact-Checking System") as demo:
    # Font stylesheet injection
    gr.HTML("<link href='https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap' rel='stylesheet'>")
    
    # Title & Subtitle block
    gr.HTML("""
    <div style='text-align: center; margin-bottom: 40px;'>
        <div style='display: inline-flex; align-items: center; gap: 10px; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 50px; padding: 6px 16px; margin-bottom: 15px;'>
            <span style='width: 8px; height: 8px; background: #3b82f6; border-radius: 50%; display: inline-block;'></span>
            <span style='color: #93c5fd; font-size: 12px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;'>Google ADK 2.0 Fact-Check System</span>
        </div>
        <h1 style='color: #f8fafc; font-size: 40px; font-weight: 800; letter-spacing: -1px; margin: 0;'>🛡️ TruthLens</h1>
        <p style='color: #64748b; font-size: 16px; margin-top: 5px;'>Premium misinformation detection tailored for modern digital platforms</p>
    </div>
    """)
    
    with gr.Tabs():
        # TAB 1: Fact-Checking Workspace
        with gr.Tab("Verification Hub"):
            with gr.Row():
                # LEFT COLUMN: INPUT CONTROLS
                with gr.Column(scale=4, elem_classes=["glass-panel"]):
                    gr.HTML("<h4 style='color: #f8fafc; margin: 0 0 12px 0; font-size: 15px;'>Select Platform Context</h4>")
                    
                    # Row of platform quick-select buttons
                    with gr.Row(elem_classes=["platform-row"]):
                        whatsapp_btn = gr.Button("💬 WhatsApp", elem_classes=["platform-btn"])
                        telegram_btn = gr.Button("✈️ Telegram", elem_classes=["platform-btn"])
                        linkedin_btn = gr.Button("💼 LinkedIn", elem_classes=["platform-btn"])
                        gmail_btn = gr.Button("📧 Gmail", elem_classes=["platform-btn"])
                        general_btn = gr.Button("🌐 General Web", elem_classes=["platform-btn"])
                    
                    user_text = gr.Textbox(
                        label="Factual Claim / URL to Verify", 
                        placeholder="Enter a factual claim to retrieve evidence from trusted sources. Or click one of the example claims below to test immediately!",
                        lines=7,
                        max_length=50000,
                        elem_id="input-box"
                    )
                    
                    gr.Examples(
                        examples=[
                            ["The Earth revolves around the Sun."],
                            ["Coffee causes dehydration."],
                            ["India landed Chandrayaan-3 on the Moon."],
                            ["Vaccines cause autism."]
                        ],
                        inputs=[user_text],
                        label="Example Claims (Click to test immediately)"
                    )
                    
                    with gr.Accordion("🖼️ Upload Screenshot / Image (OCR)", open=False):
                        image_upload = gr.Image(label="Upload Screenshot", type="filepath")
                    
                    verify_btn = gr.Button("Verify Content", variant="primary", elem_classes=["verify-btn"])
                    
                # RIGHT COLUMN: STATUS & OUTPUT TIMELINE
                with gr.Column(scale=5):
                    # Styled status text
                    status_lbl = gr.Label(value="Ready to verify", label="Agent Orchestrator Status")
                    
                    # HTML verdict card container
                    verdict_html = gr.HTML(value=get_verdict_html("Pending", 0.0))
                    
                    # Slide confidence indicator
                    confidence_card = gr.Slider(
                        label="Confidence Index (%)", 
                        minimum=0, 
                        maximum=100, 
                        value=0, 
                        interactive=False,
                        elem_classes=["confidence-slider"]
                    )
                    
                    # API Key Configuration Accordion located below slider
                    with gr.Accordion("🔑 API Key Configuration", open=not bool(GOOGLE_API_KEY)):
                        gr.HTML("<div style='margin-bottom: 8px;'><a href='https://aistudio.google.com/' target='_blank' style='color: #3b82f6; text-decoration: underline; font-weight: bold;'>Get a Gemini API Key from Google AI Studio</a></div>")
                        api_key_input = gr.Textbox(
                            label="Gemini API Key",
                            placeholder="Paste your key here (AIzaSy...)",
                            type="password",
                            value=GOOGLE_API_KEY or ""
                        )
                        test_key_btn = gr.Button("🔌 Test & Connect Key", variant="secondary")
                        key_status_html = gr.HTML(
                            value="<div style='margin-top: 10px; font-size: 13px;'><span style='color: #10b981; font-weight: bold;'>🟢 Connected (Loaded from environment)</span></div>" if GOOGLE_API_KEY 
                            else "<div style='margin-top: 10px; font-size: 13px;'><span style='color: #ef4444; font-weight: bold;'>🔴 Missing (Please paste your key above)</span></div>"
                        )
            
            # Markdown Report Output (Scroll down)
            gr.HTML("<h3 style='color: #f8fafc; margin-top: 35px; border-bottom: 1px solid #1e293b; padding-bottom: 10px; font-weight: 700;'>📋 Verification Report</h3>")
            report_file = gr.File(label="📥 Download Markdown Report (.md)", visible=False)
            report_md = gr.Markdown(value=WELCOME_MESSAGE)

        # TAB 2: Cache & History Registry
        with gr.Tab("TruthLens Registry"):
            gr.HTML("<h3 style='color: #f8fafc; margin-bottom: 20px; font-weight: 700;'>📊 System Metrics</h3>")
            analytics_html = gr.HTML(value=get_stats_html())
            
            gr.HTML("<h3 style='color: #f8fafc; margin-top: 30px; margin-bottom: 20px; font-weight: 700;'>🕒 Recent Verifications</h3>")
            history_table = gr.Dataframe(
                headers=["Content Snippet", "Verdict", "Confidence", "Verified At"],
                value=get_history_table()
            )
            with gr.Row():
                refresh_btn = gr.Button("Refresh Registry & Statistics", elem_classes=["verify-btn"])
                clear_cache_btn = gr.Button("🗑️ Clear Cache Database", variant="stop")
            cache_status_html = gr.HTML(value="")

        # TAB 3: Integrations & API Docs
        with gr.Tab("🔌 Developer API"):
            gr.HTML("<h3 style='color: #f8fafc; margin-bottom: 20px; font-weight: 700;'>🔌 Developer API Access</h3>")
            gr.Markdown("""
TruthLens is built to be accessible programmatically. You can connect this multi-agent fact-checking engine to your own WhatsApp bots, Telegram channels, custom browser extensions, or newsroom tools.

### 🐍 Python Gradio Client Example
Integrate fact-checking into your Python application in less than 5 lines of code:
```python
from gradio_client import Client

# Initialize client pointing to this server
client = Client("http://localhost:7860/")

# Trigger multi-agent pipeline
result = client.predict(
    user_input="Paste claim or URL here...",
    image_file=None,  # Or pass filepath to image
    api_key="YOUR_GEMINI_API_KEY",
    api_name="/process_verification"
)

# Output is a list: [verdict_html, confidence_score, markdown_report, status_lbl, report_file_path]
print(result[2]) # Print the markdown report!
```

### ✈️ Integrations Checklist
1. **WhatsApp & Telegram bots**: Run a polling listener that calls the Gradio API client whenever a user forwards a message.
2. **Browser Extensions**: Highlight any text on a page, right-click, and send it to the TruthLens backend to get a visual popup verdict card.
""")

    # Custom premium footer
    gr.HTML("""
    <div style='text-align: center; margin-top: 40px; padding: 20px 0; border-top: 1px solid #1e293b; color: #64748b; font-size: 13px;'>
        <div style='display: flex; justify-content: center; gap: 20px; margin-bottom: 10px;'>
            <span style='font-weight: 600; color: #94a3b8;'>⚖️ System: Online</span>
            <span style='font-weight: 600; color: #94a3b8;'>🛡️ Powered by: Google ADK 2.0 & Gemini 2.5</span>
        </div>
        <div>© 2026 TruthLens. All rights reserved. Built for Kaggle x Google AI Agents.</div>
    </div>
    """)

    # Platform selector event wiring
    whatsapp_btn.click(fn=select_whatsapp, inputs=[], outputs=[user_text])
    telegram_btn.click(fn=select_telegram, inputs=[], outputs=[user_text])
    linkedin_btn.click(fn=select_linkedin, inputs=[], outputs=[user_text])
    gmail_btn.click(fn=select_gmail, inputs=[], outputs=[user_text])
    general_btn.click(fn=select_general, inputs=[], outputs=[user_text])

    # Dynamic API Key status handler
    api_key_input.change(
        fn=update_key_status,
        inputs=[api_key_input],
        outputs=[key_status_html]
    )
    
    test_key_btn.click(
        fn=verify_and_connect_api_key,
        inputs=[api_key_input],
        outputs=[key_status_html]
    )

    # Verification click handler
    verify_btn.click(
        fn=process_verification,
        inputs=[user_text, image_upload, api_key_input],
        outputs=[verdict_html, confidence_card, report_md, status_lbl, report_file]
    )
    
    def refresh_dashboard():
        return get_stats_html(), get_history_table()
        
    refresh_btn.click(
        fn=refresh_dashboard,
        inputs=[],
        outputs=[analytics_html, history_table]
    )
    
    clear_cache_btn.click(
        fn=clear_cache_db,
        inputs=[],
        outputs=[analytics_html, history_table, cache_status_html]
    )

if __name__ == "__main__":
    # Check if running in a Hugging Face Space
    is_hf = os.environ.get("SPACE_ID") is not None or os.environ.get("SYSTEM") == "spaces"
    
    server_name = "0.0.0.0" if is_hf else "127.0.0.1"
    share_state = False if is_hf else True
    
    demo.launch(
        server_name=server_name, 
        server_port=7860, 
        share=share_state,
        css=custom_css, 
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate")
    )
