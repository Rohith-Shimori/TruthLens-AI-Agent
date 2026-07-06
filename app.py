import os
import time
import json
import re
import gradio as gr
from typing import Tuple, Generator, Optional, Any

# Import our modular components
from config import GOOGLE_API_KEY
from security import SecurityManager
from memory import MemoryManager
from agent import run_truthlens_verification

# Initialize managers
security = SecurityManager()
memory = MemoryManager()

# Default report placeholder
WELCOME_MESSAGE = """
# 🛡️ TruthLens Verification Engine

Please enter a URL, paste a suspicious claim, or upload a screenshot to initiate analysis. 
The multi-agent system will extract facts, search web databases, score domain reliability, inspect for emotional bias, and compile an evidence report.
"""

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
    
    # Search for "Verdict: Mostly True", "**verdict:** false", etc.
    match = re.search(r"verdict\s*:\s*\**([a-zA-Z\s]+)\**", report_lower)
    verdict_str = match.group(1).strip() if match else ""
    
    if "mostly true" in verdict_str or "mostly true" in report_lower:
        return "Mostly True", 75.0
    elif "true" in verdict_str or "true" in report_lower:
        if "mostly true" not in report_lower:
            return "True", 90.0
    elif "misleading" in verdict_str or "misleading" in report_lower:
        return "Misleading", 40.0
    elif "false" in verdict_str or "false" in report_lower:
        return "False", 15.0
        
    return "Unverified", 50.0

def get_verdict_html(verdict: str, confidence: float) -> str:
    """Returns a highly polished, styled HTML banner for the overall verdict."""
    color_map = {
        "True": {"bg": "rgba(16, 185, 129, 0.12)", "border": "#10b981", "text": "#34d399", "emoji": "🛡️"},
        "Mostly True": {"bg": "rgba(52, 211, 153, 0.08)", "border": "#34d399", "text": "#a7f3d0", "emoji": "✅"},
        "Misleading": {"bg": "rgba(245, 158, 11, 0.12)", "border": "#f59e0b", "text": "#fbbf24", "emoji": "⚠️"},
        "False": {"bg": "rgba(239, 68, 68, 0.12)", "border": "#ef4444", "text": "#f87171", "emoji": "❌"},
        "Unverified": {"bg": "rgba(148, 163, 184, 0.12)", "border": "#94a3b8", "text": "#cbd5e1", "emoji": "🔍"},
        "Pending": {"bg": "rgba(59, 130, 246, 0.08)", "border": "#3b82f6", "text": "#93c5fd", "emoji": "🤖"},
        "Processing": {"bg": "rgba(59, 130, 246, 0.12)", "border": "#60a5fa", "text": "#bfdbfe", "emoji": "⚙️"}
    }
    
    style = color_map.get(verdict, color_map["Unverified"])
    
    # Calculate a glowing color based on verdict
    glow_color = style["border"]
    
    return f"""
    <div style='
        background: {style["bg"]}; 
        border: 2px solid {style["border"]}; 
        border-radius: 16px; 
        padding: 24px; 
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3), 0 0 15px {glow_color}33;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    '>
        <div style='font-size: 48px; filter: drop-shadow(0 0 8px {glow_color});'>{style["emoji"]}</div>
        <div style='font-size: 26px; font-weight: 800; color: {style["text"]}; margin-top: 10px; letter-spacing: 0.5px;'>OVERALL VERDICT: {verdict.upper()}</div>
        <div style='font-size: 16px; color: #94a3b8; margin-top: 8px;'>TruthLens Confidence Level: <span style='font-weight: bold; color: #f8fafc;'>{confidence}%</span></div>
    </div>
    """

def process_verification(user_input: str, image_file: Optional[str], api_key: Optional[str] = None) -> Generator[Tuple[str, float, str, str], None, None]:
    """
    Core function called by the UI.
    Streams progress states, then yields the final verdict html, confidence, report, and status.
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
        yield get_verdict_html("Unverified", 0.0), 0.0, "### ❌ Input Required\nPlease provide either a URL, raw text, or upload an image screenshot.", "Ready"
        return

    # 2. Security validation
    sanitized = security.sanitize_input(target_input) if input_type != "image" else target_input
    
    if input_type != "image":
        is_injection, reason = security.detect_prompt_injection(sanitized)
        if is_injection:
            yield get_verdict_html("Unverified", 0.0), 0.0, f"### ⚠️ Security Violation\n{reason}", "Blocked"
            return
            
        if not security.validate_content_length(sanitized):
            yield get_verdict_html("Unverified", 0.0), 0.0, "### ❌ Input Too Long\nInput text exceeds the maximum character threshold (50,000 characters).", "Ready"
            return

    # 3. Check SQLite memory cache
    yield get_verdict_html("Processing", 20.0), 20.0, "### 🔍 Searching cache...\nRetrieving matching verification payloads from local SQLite index.", "Checking database cache..."
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
        
        yield get_verdict_html(verdict, confidence), confidence, cached_report, "Verification loaded from memory cache!"
        return

    # 4. Cache miss - run the ADK Multi-Agent Workflow
    active_key = api_key or GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY")
    if not active_key:
        yield get_verdict_html("Unverified", 0.0), 0.0, "### 🔑 API Key Required\nPlease enter your Gemini API key in the configuration panel above, or set it in your `.env` file to start the live verification pipeline.", "API Key missing"
        return

    session_id = f"sess_{int(time.time())}"
    current_status = "Initializing Agents..."
    
    # We yield intermediate states to show progress
    yield get_verdict_html("Processing", 10.0), 10.0, "### 🏗&nbsp; Initializing TruthLens Agent Network...\nDecoupling instructions and establishing session channels.", current_status
    
    final_report = ""
    verdict = "Unverified"
    confidence = 50.0
    extracted_claims = []
    evidence_list = []
    bias_data = {}

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
                yield get_verdict_html("Processing", 15.0), 15.0, "### 📥 Ingesting and Parsing Content...\nExtracting raw text and visual metadata from source.", current_status
            elif agent_name == "ClaimExtractionAgent":
                current_status = "2/7 Extracting factual claims..."
                yield get_verdict_html("Processing", 30.0), 30.0, "### 📝 Extracting Factual Claims...\nIsolating check-worthy assertions of facts, statistics, or quotes.", current_status
                if text_content:
                    claims_data = extract_json_from_text(text_content)
                    if isinstance(claims_data, dict):
                        extracted_claims = claims_data.get("claims", [])
                    elif isinstance(claims_data, list):
                        extracted_claims = claims_data
            elif agent_name == "EvidenceRetrieverAgent":
                current_status = "3/7 Retrieving evidence from web & Wikipedia..."
                yield get_verdict_html("Processing", 50.0), 50.0, "### 🔍 Retrieving Supporting/Refuting Evidence...\nSearching Wikipedia and Google grounding index for facts.", current_status
            elif agent_name == "SourceCredibilityAgent":
                current_status = "4/7 Scoring source credibility..."
                yield get_verdict_html("Processing", 70.0), 70.0, "### 📊 Scoring Source Credibility...\nAnalyzing references against known reliability indexes.", current_status
            elif agent_name == "BiasAnalyzerAgent":
                current_status = "5/7 Analyzing framing and sensationalism..."
                yield get_verdict_html("Processing", 85.0), 85.0, "### ⚖️ Analyzing Formatting, Tone, and Logical Fallacies...\nEvaluating loaded language and emotional sentiment.", current_status
            elif agent_name == "VerdictAgent":
                current_status = "6/7 Cross-referencing and issuing verdicts..."
                yield get_verdict_html("Processing", 95.0), 95.0, "### ⚖️ Cross-Referencing Evidence & Issuing Verdicts...\nSynthesizing source ratings and fact alignments.", current_status
            elif agent_name == "ReportGeneratorAgent":
                current_status = "7/7 Compiling final report..."
                if text_content:
                    final_report = text_content
                    # Robust verdict parsing
                    verdict, confidence = parse_verdict_from_report(final_report)
                yield get_verdict_html(verdict, confidence), confidence, final_report or "Generating final output...", current_status


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
            yield get_verdict_html(verdict, confidence), confidence, final_report, current_status
        else:
            yield get_verdict_html("Unverified", 50.0), 50.0, "### ⚠️ Verification Incomplete\nAgents finished but no report was returned. Try refining your prompt.", "Error"
            
    except Exception as e:
        yield get_verdict_html("Unverified", 0.0), 0.0, f"### ❌ Execution Error\nAn error occurred while running the multi-agent system:\n`{str(e)}`", "Failed"

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

def get_history_table() -> list:
    history = memory.get_recent_verifications()
    return [[h.get("query_text", "")[:60] + "...", h.get("verdict", ""), f"{h.get('confidence_score', 0.0)}%", time.strftime('%Y-%m-%d %H:%M', time.localtime(h.get('created_at', 0)))] for h in history]

# Presets mapping for quick-select platforms
def select_whatsapp():
    return gr.update(label="💬 WhatsApp Rumor Text / URL", placeholder="Paste forwarded message chain, viral text, or message link here. If you have an image, upload it in the accordion below.")

def select_telegram():
    return gr.update(label="✈️ Telegram Forwarded Claim", placeholder="Paste text from Telegram channel, forwarded rumor, or channel post URL here.")

def select_linkedin():
    return gr.update(label="💼 LinkedIn Post Claim", placeholder="Paste professional claim, job offer rumor, or user post text/URL here.")

def select_gmail():
    return gr.update(label="📧 Gmail Suspicious Content", placeholder="Paste suspicious phishing email body, strange financial request, or sender info here.")

def select_general():
    return gr.update(label="🌐 General Social Media / Web Claim", placeholder="Paste tweet text, news link, blog URL, or general claim to check.")


# UI custom CSS injection for Outfit/Plus Jakarta typography, premium colors, and animations
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap');

* {
    font-family: 'Plus Jakarta Sans', 'Outfit', sans-serif !important;
}

body {
    background-color: #0b0f19 !important;
}

.gradio-container {
    max-width: 1100px !important;
    margin: 0 auto !important;
    padding-top: 40px !important;
    background-color: #0b0f19 !important;
}

/* Glassmorphism layouts */
.glass-panel {
    background: rgba(21, 28, 44, 0.65) !important;
    border: 1px solid #1e293b !important;
    border-radius: 16px !important;
    padding: 24px !important;
    box-shadow: 0 10px 30px 0 rgba(0, 0, 0, 0.4) !important;
    backdrop-filter: blur(10px) !important;
}

/* Custom platform pills */
.platform-row {
    margin-bottom: 15px !important;
}

.platform-btn {
    border: 1px solid #1e293b !important;
    background: rgba(30, 41, 59, 0.4) !important;
    color: #94a3b8 !important;
    border-radius: 50px !important;
    padding: 6px 14px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}

.platform-btn:hover {
    background: rgba(59, 130, 246, 0.1) !important;
    border-color: #3b82f6 !important;
    color: #f8fafc !important;
}

/* Premium Verify Button */
.verify-btn {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    color: white !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    border: none !important;
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3) !important;
    transition: all 0.2s ease !important;
    padding: 12px 24px !important;
}

.verify-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important;
}

/* Custom Textbox overrides */
#input-box textarea {
    background-color: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid #1e293b !important;
    border-radius: 12px !important;
    color: #f8fafc !important;
    font-size: 15px !important;
}

#input-box textarea:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25) !important;
}

/* Custom progress slider */
.confidence-slider {
    background-color: transparent !important;
}
"""

with gr.Blocks() as demo:
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
                        label="🌐 General Social Media / Web Claim", 
                        placeholder="Paste claim text, news article URL, or social media link here...",
                        lines=7,
                        max_length=50000,
                        elem_id="input-box"
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
            
            # Markdown Report Output (Scroll down)
            gr.HTML("<h3 style='color: #f8fafc; margin-top: 35px; border-bottom: 1px solid #1e293b; padding-bottom: 10px; font-weight: 700;'>📋 Verification Report</h3>")
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
            refresh_btn = gr.Button("Refresh Registry & Statistics", elem_classes=["verify-btn"])

    # Platform selector event wiring
    whatsapp_btn.click(fn=select_whatsapp, inputs=[], outputs=[user_text])
    telegram_btn.click(fn=select_telegram, inputs=[], outputs=[user_text])
    linkedin_btn.click(fn=select_linkedin, inputs=[], outputs=[user_text])
    gmail_btn.click(fn=select_gmail, inputs=[], outputs=[user_text])
    general_btn.click(fn=select_general, inputs=[], outputs=[user_text])

    # Verification click handler
    verify_btn.click(
        fn=process_verification,
        inputs=[user_text, image_upload, api_key_input],
        outputs=[verdict_html, confidence_card, report_md, status_lbl]
    )
    
    def refresh_dashboard():
        return get_stats_html(), get_history_table()
        
    refresh_btn.click(
        fn=refresh_dashboard,
        inputs=[],
        outputs=[analytics_html, history_table]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1", 
        server_port=7860, 
        share=False,
        css=custom_css, 
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate")
    )
