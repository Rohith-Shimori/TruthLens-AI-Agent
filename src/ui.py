import html
import gradio as gr

# Default report placeholder (Premium Landing Intro)
WELCOME_MESSAGE = """
# 🛡️ TruthLens Fact-Checking Report

### Enter a factual claim to retrieve evidence from trusted sources.

TruthLens leverages a network of 7 specialized AI agents to analyze content credibility, bias, and consensus. 
To begin, paste a claim in the input field, upload a screenshot of a forwarded message, or pick one of the sample claims below.
"""

# ============================================================
# PREMIUM CSS — Animated dark glassmorphism with micro-interactions
# ============================================================
custom_css = """
/* ═══════════════════════════════════════════════════════════
   1. ROOT VARIABLES & GLOBAL RESET
   ═══════════════════════════════════════════════════════════ */
:root, .dark {
    --bg-primary: #06080f;
    --bg-secondary: #0c1121;
    --bg-glass: rgba(12, 17, 33, 0.65);
    --bg-glass-hover: rgba(20, 30, 60, 0.75);
    --border-subtle: rgba(56, 78, 133, 0.25);
    --border-glow: rgba(59, 130, 246, 0.5);
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-heading: #f1f5f9;
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;
    --accent-purple: #8b5cf6;
    --accent-green: #10b981;

    --background-fill-primary: var(--bg-primary) !important;
    --background-fill-secondary: var(--bg-secondary) !important;
    --block-background-fill: var(--bg-glass) !important;
    --block-border-color: var(--border-subtle) !important;
    --block-border-width: 1px !important;
    --body-text-color: var(--text-primary) !important;
    --body-text-color-subdued: var(--text-secondary) !important;
    --block-title-text-color: var(--text-heading) !important;
    --block-label-text-color: var(--text-secondary) !important;
    --input-text-color: var(--text-heading) !important;
    --input-placeholder-color: #475569 !important;
    --input-background-fill: rgba(10, 15, 30, 0.85) !important;
    --input-border-color: var(--border-subtle) !important;
    --input-border-width: 1px !important;
    --button-primary-background-fill: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%) !important;
    --button-primary-background-fill-hover: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%) !important;
    --button-primary-text-color: white !important;
    --button-secondary-background-fill: rgba(30, 41, 59, 0.4) !important;
    --button-secondary-background-fill-hover: rgba(59, 130, 246, 0.12) !important;
    --button-secondary-text-color: var(--text-secondary) !important;
    --button-secondary-border-color: var(--border-subtle) !important;
    --table-border-color: var(--border-subtle) !important;
    --table-header-background-fill: rgba(30, 41, 59, 0.6) !important;
    --table-row-background-fill: rgba(10, 15, 30, 0.4) !important;
}

* { font-family: 'Plus Jakarta Sans', 'Outfit', system-ui, sans-serif !important; }
body { background-color: var(--bg-primary) !important; color: var(--text-primary) !important; }

.gradio-container {
    max-width: 1200px !important;
    margin: 0 auto !important;
    padding-top: 20px !important;
    background-color: var(--bg-primary) !important;
}

footer { display: none !important; }

/* ═══════════════════════════════════════════════════════════
   2. KEYFRAME ANIMATIONS
   ═══════════════════════════════════════════════════════════ */
@keyframes gradient-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.3), 0 0 40px rgba(124, 58, 237, 0.1); }
    50% { box-shadow: 0 0 30px rgba(59, 130, 246, 0.5), 0 0 60px rgba(124, 58, 237, 0.2); }
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-4px); }
}

@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(15px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes spin-slow {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@keyframes border-pulse {
    0%, 100% { border-color: rgba(59, 130, 246, 0.3); }
    50% { border-color: rgba(124, 58, 237, 0.5); }
}

/* ═══════════════════════════════════════════════════════════
   3. GLASSMORPHISM PANELS
   ═══════════════════════════════════════════════════════════ */
.glass-panel {
    background: var(--bg-glass) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 20px !important;
    padding: 28px !important;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.03) !important;
    backdrop-filter: blur(16px) !important;
    animation: fadeInUp 0.5s ease-out !important;
}

/* ═══════════════════════════════════════════════════════════
   4. PLATFORM PILLS
   ═══════════════════════════════════════════════════════════ */
.platform-row { margin-bottom: 16px !important; gap: 8px !important; }

.platform-btn {
    border: 1px solid var(--border-subtle) !important;
    background: rgba(15, 23, 42, 0.5) !important;
    color: var(--text-secondary) !important;
    border-radius: 50px !important;
    padding: 7px 16px !important;
    font-size: 12.5px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    letter-spacing: 0.3px !important;
}

.platform-btn:hover {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(124, 58, 237, 0.1)) !important;
    border-color: var(--accent-blue) !important;
    color: var(--text-heading) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2) !important;
}

/* ═══════════════════════════════════════════════════════════
   5. VERIFY BUTTON — Premium Animated CTA
   ═══════════════════════════════════════════════════════════ */
.verify-btn {
    background: linear-gradient(135deg, #2563eb 0%, #7c3aed 50%, #2563eb 100%) !important;
    background-size: 200% 200% !important;
    animation: gradient-shift 3s ease infinite, pulse-glow 2s ease-in-out infinite !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    border-radius: 14px !important;
    border: none !important;
    padding: 14px 28px !important;
    cursor: pointer !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    letter-spacing: 0.5px !important;
    text-transform: uppercase !important;
}

.verify-btn:hover {
    transform: translateY(-3px) scale(1.02) !important;
    box-shadow: 0 8px 30px rgba(37, 99, 235, 0.5), 0 0 50px rgba(124, 58, 237, 0.2) !important;
}

.verify-btn:active {
    transform: translateY(0) scale(0.98) !important;
}

/* ═══════════════════════════════════════════════════════════
   6. INPUT TEXTBOX — Premium Styled
   ═══════════════════════════════════════════════════════════ */
#input-box textarea {
    background-color: rgba(10, 15, 30, 0.85) !important;
    border: 1.5px solid var(--border-subtle) !important;
    border-radius: 14px !important;
    color: var(--text-heading) !important;
    font-size: 15px !important;
    line-height: 1.6 !important;
    padding: 16px !important;
    transition: all 0.3s ease !important;
}

#input-box textarea:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15), 0 0 20px rgba(59, 130, 246, 0.08) !important;
}

/* ═══════════════════════════════════════════════════════════
   7. TABS — Premium Icons & Animated Underline
   ═══════════════════════════════════════════════════════════ */
.tabs > .tab-nav > button {
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: 0.5px !important;
    color: var(--text-secondary) !important;
    padding: 12px 24px !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.3s ease !important;
    background: transparent !important;
}

.tabs > .tab-nav > button:hover {
    color: var(--text-heading) !important;
    background: rgba(59, 130, 246, 0.06) !important;
}

.tabs > .tab-nav > button.selected {
    color: var(--accent-blue) !important;
    border-bottom: 2px solid var(--accent-blue) !important;
    background: rgba(59, 130, 246, 0.08) !important;
}

/* ═══════════════════════════════════════════════════════════
   8. CONFIDENCE SLIDER
   ═══════════════════════════════════════════════════════════ */
.confidence-slider { background-color: transparent !important; }

.confidence-slider input[type="range"]::-webkit-slider-runnable-track {
    background: linear-gradient(90deg, #ef4444 0%, #f59e0b 40%, #10b981 100%) !important;
    border-radius: 6px !important;
    height: 8px !important;
}

/* ═══════════════════════════════════════════════════════════
   9. MARKDOWN REPORT STYLING
   ═══════════════════════════════════════════════════════════ */
.prose p, .prose li, .prose span, .prose ul, .prose ol, .prose strong {
    color: var(--text-primary) !important;
}

.prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6 {
    color: var(--text-heading) !important;
    font-weight: 700 !important;
}

.prose blockquote {
    border-left: 3px solid var(--accent-blue) !important;
    color: var(--text-secondary) !important;
    background: rgba(30, 41, 59, 0.25) !important;
    border-radius: 0 10px 10px 0 !important;
    padding: 12px 16px !important;
}

.prose code {
    color: #60a5fa !important;
    background: rgba(15, 23, 42, 0.7) !important;
    border-radius: 6px !important;
    padding: 2px 6px !important;
}

.prose pre {
    background: rgba(10, 15, 30, 0.9) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 12px !important;
}

/* ═══════════════════════════════════════════════════════════
   10. FILE DOWNLOAD COMPONENT
   ═══════════════════════════════════════════════════════════ */
.file-preview {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid var(--accent-blue) !important;
    border-radius: 14px !important;
}

/* ═══════════════════════════════════════════════════════════
   11. ACCORDION STYLING
   ═══════════════════════════════════════════════════════════ */
.accordion { border: 1px solid var(--border-subtle) !important; border-radius: 14px !important; }

/* ═══════════════════════════════════════════════════════════
   12. EXAMPLES / SAMPLE CLAIMS — Card Style
   ═══════════════════════════════════════════════════════════ */
.examples-table button {
    background: rgba(15, 23, 42, 0.6) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    padding: 10px 16px !important;
    transition: all 0.3s ease !important;
    font-size: 13px !important;
}

.examples-table button:hover {
    background: rgba(59, 130, 246, 0.12) !important;
    border-color: var(--accent-blue) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.15) !important;
}

/* ═══════════════════════════════════════════════════════════
   13. SCROLLBAR STYLING
   ═══════════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb { background: rgba(59, 130, 246, 0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(59, 130, 246, 0.5); }

/* ═══════════════════════════════════════════════════════════
   14. LOADING STATES
   ═══════════════════════════════════════════════════════════ */
.generating {
    border: 1px solid var(--accent-blue) !important;
    animation: border-pulse 1.5s ease-in-out infinite !important;
}
"""


# ============================================================
# HERO HEADER HTML — Animated gradient with floating shield
# ============================================================
HERO_HEADER_HTML = """
<div style='
    text-align: center; 
    margin-bottom: 35px;
    padding: 30px 20px 25px;
    position: relative;
    overflow: hidden;
'>
    <!-- Animated gradient background -->
    <div style='
        position: absolute; top: 0; left: 0; right: 0; bottom: 0;
        background: radial-gradient(ellipse at 30% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 60%),
                    radial-gradient(ellipse at 70% 30%, rgba(124, 58, 237, 0.06) 0%, transparent 50%);
        pointer-events: none;
    '></div>
    
    <!-- Badge -->
    <div style='
        display: inline-flex; align-items: center; gap: 8px;
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(124, 58, 237, 0.08));
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 50px; padding: 7px 18px; margin-bottom: 18px;
    '>
        <span style='width: 7px; height: 7px; background: linear-gradient(135deg, #3b82f6, #8b5cf6); border-radius: 50%; display: inline-block; animation: pulse-glow 2s ease-in-out infinite;'></span>
        <span style='color: #93c5fd; font-size: 11.5px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;'>Google ADK 2.0 × Gemini 2.5 Flash</span>
    </div>
    
    <!-- Main Title -->
    <div style='position: relative;'>
        <h1 style='
            color: transparent;
            background: linear-gradient(135deg, #e2e8f0 0%, #3b82f6 40%, #8b5cf6 70%, #e2e8f0 100%);
            background-size: 200% auto;
            background-clip: text;
            -webkit-background-clip: text;
            font-size: 52px; font-weight: 800; letter-spacing: -2px; margin: 0;
            animation: gradient-shift 4s linear infinite;
            line-height: 1.1;
        '>🛡️ TruthLens</h1>
        <p style='
            color: #64748b; font-size: 15px; margin-top: 8px; font-weight: 400;
            letter-spacing: 0.5px;
        '>AI-Powered Multi-Agent Misinformation Detection Engine</p>
    </div>

    <!-- Feature pills -->
    <div style='display: flex; justify-content: center; gap: 12px; margin-top: 18px; flex-wrap: wrap;'>
        <span style='
            display: inline-flex; align-items: center; gap: 5px;
            background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25);
            border-radius: 50px; padding: 5px 14px; font-size: 11.5px; color: #6ee7b7; font-weight: 600;
        '>🤖 7 Specialized Agents</span>
        <span style='
            display: inline-flex; align-items: center; gap: 5px;
            background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.25);
            border-radius: 50px; padding: 5px 14px; font-size: 11.5px; color: #93c5fd; font-weight: 600;
        '>🔗 MCP Protocol</span>
        <span style='
            display: inline-flex; align-items: center; gap: 5px;
            background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.25);
            border-radius: 50px; padding: 5px 14px; font-size: 11.5px; color: #c4b5fd; font-weight: 600;
        '>🖼️ Multimodal OCR</span>
        <span style='
            display: inline-flex; align-items: center; gap: 5px;
            background: rgba(6, 182, 212, 0.1); border: 1px solid rgba(6, 182, 212, 0.25);
            border-radius: 50px; padding: 5px 14px; font-size: 11.5px; color: #67e8f9; font-weight: 600;
        '>🛡️ SSRF + XSS Protected</span>
    </div>
</div>
"""


# ============================================================
# AGENT PIPELINE VISUAL — Shows the 7-agent flow
# ============================================================
PIPELINE_VISUAL_HTML = """
<div style='
    display: flex; align-items: center; justify-content: center; gap: 6px;
    padding: 14px 16px; margin: 15px 0 20px;
    background: rgba(12, 17, 33, 0.5);
    border: 1px solid rgba(56, 78, 133, 0.2);
    border-radius: 14px;
    overflow-x: auto;
    flex-wrap: wrap;
'>
    <div style='display: flex; align-items: center; gap: 4px; background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 8px; padding: 6px 10px; font-size: 10.5px; color: #93c5fd; font-weight: 600; white-space: nowrap;'>
        📥 Input
    </div>
    <span style='color: #334155; font-size: 14px;'>→</span>
    <div style='display: flex; align-items: center; gap: 4px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; padding: 6px 10px; font-size: 10.5px; color: #6ee7b7; font-weight: 600; white-space: nowrap;'>
        🔍 ClaimExtractor
    </div>
    <span style='color: #334155; font-size: 14px;'>→</span>
    <div style='display: flex; align-items: center; gap: 4px; background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: 8px; padding: 6px 10px; font-size: 10.5px; color: #c4b5fd; font-weight: 600; white-space: nowrap;'>
        🌐 EvidenceHunter
    </div>
    <span style='color: #334155; font-size: 14px;'>→</span>
    <div style='display: flex; align-items: center; gap: 4px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 8px; padding: 6px 10px; font-size: 10.5px; color: #fbbf24; font-weight: 600; white-space: nowrap;'>
        ✅ FactChecker
    </div>
    <span style='color: #334155; font-size: 14px;'>→</span>
    <div style='display: flex; align-items: center; gap: 4px; background: rgba(236, 72, 153, 0.1); border: 1px solid rgba(236, 72, 153, 0.25); border-radius: 8px; padding: 6px 10px; font-size: 10.5px; color: #f9a8d4; font-weight: 600; white-space: nowrap;'>
        ⚖️ BiasAnalyzer
    </div>
    <span style='color: #334155; font-size: 14px;'>→</span>
    <div style='display: flex; align-items: center; gap: 4px; background: rgba(6, 182, 212, 0.1); border: 1px solid rgba(6, 182, 212, 0.25); border-radius: 8px; padding: 6px 10px; font-size: 10.5px; color: #67e8f9; font-weight: 600; white-space: nowrap;'>
        📊 Verdict
    </div>
    <span style='color: #334155; font-size: 14px;'>→</span>
    <div style='display: flex; align-items: center; gap: 4px; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 6px 10px; font-size: 10.5px; color: #6ee7b7; font-weight: 600; white-space: nowrap;'>
        📝 Report
    </div>
</div>
"""


# ============================================================
# PREMIUM FOOTER
# ============================================================
FOOTER_HTML = """
<div style='
    text-align: center; margin-top: 50px; padding: 25px 0 15px; 
    border-top: 1px solid rgba(56, 78, 133, 0.2); 
    color: #475569; font-size: 12.5px;
'>
    <div style='display: flex; justify-content: center; gap: 24px; margin-bottom: 12px; flex-wrap: wrap;'>
        <span style='display: inline-flex; align-items: center; gap: 5px; font-weight: 600; color: #64748b;'>
            <span style='width: 6px; height: 6px; background: #10b981; border-radius: 50%; display: inline-block;'></span>
            System Online
        </span>
        <span style='font-weight: 600; color: #64748b;'>🛡️ Powered by Google ADK 2.0 × Gemini 2.5</span>
        <span style='font-weight: 600; color: #64748b;'>✅ 24/24 Eval Tests Passed</span>
    </div>
    <div style='color: #334155;'>© 2026 TruthLens • Kaggle × Google AI Agents Capstone</div>
</div>
"""


# ============================================================
# VERDICT CARD — Premium Animated HTML
# ============================================================
def get_verdict_html(verdict: str, confidence: float) -> str:
    """Returns a customized premium HTML container for the verdict badge and confidence."""
    v_clean = verdict.strip().lower()
    
    verdict_styles = {
        "true": {
            "emoji": "✅", "label": "VERIFIED TRUE",
            "bg": "linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(16, 185, 129, 0.05))",
            "border": "rgba(16, 185, 129, 0.5)", "text": "#10b981", "glow": "#10b981",
            "bar_color": "linear-gradient(90deg, #10b981, #34d399)"
        },
        "mostly true": {
            "emoji": "✓", "label": "MOSTLY TRUE",
            "bg": "linear-gradient(135deg, rgba(52, 211, 153, 0.12), rgba(52, 211, 153, 0.05))",
            "border": "rgba(52, 211, 153, 0.5)", "text": "#34d399", "glow": "#34d399",
            "bar_color": "linear-gradient(90deg, #34d399, #6ee7b7)"
        },
        "misleading": {
            "emoji": "⚠️", "label": "MISLEADING",
            "bg": "linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(245, 158, 11, 0.05))",
            "border": "rgba(245, 158, 11, 0.5)", "text": "#f59e0b", "glow": "#f59e0b",
            "bar_color": "linear-gradient(90deg, #f59e0b, #fbbf24)"
        },
        "false": {
            "emoji": "❌", "label": "VERIFIED FALSE",
            "bg": "linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(239, 68, 68, 0.05))",
            "border": "rgba(239, 68, 68, 0.5)", "text": "#ef4444", "glow": "#ef4444",
            "bar_color": "linear-gradient(90deg, #ef4444, #f87171)"
        },
        "unverified": {
            "emoji": "🔍", "label": "UNVERIFIED",
            "bg": "linear-gradient(135deg, rgba(100, 116, 139, 0.12), rgba(100, 116, 139, 0.05))",
            "border": "rgba(100, 116, 139, 0.4)", "text": "#94a3b8", "glow": "#64748b",
            "bar_color": "linear-gradient(90deg, #64748b, #94a3b8)"
        },
        "pending": {
            "emoji": "⏳", "label": "AWAITING INPUT",
            "bg": "linear-gradient(135deg, rgba(71, 85, 105, 0.1), rgba(71, 85, 105, 0.05))",
            "border": "rgba(71, 85, 105, 0.3)", "text": "#64748b", "glow": "#475569",
            "bar_color": "linear-gradient(90deg, #475569, #64748b)"
        },
        "processing": {
            "emoji": "⚡", "label": "AGENTS PROCESSING",
            "bg": "linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(124, 58, 237, 0.08))",
            "border": "rgba(59, 130, 246, 0.5)", "text": "#3b82f6", "glow": "#3b82f6",
            "bar_color": "linear-gradient(90deg, #3b82f6, #8b5cf6)"
        }
    }
    
    style = verdict_styles.get(v_clean, verdict_styles["unverified"])
    glow_color = style["glow"]
    safe_verdict = html.escape(style.get("label", verdict.upper()))
    bar_width = max(min(confidence, 100), 0)
    
    # Processing state gets an animated shimmer bar
    bar_extra = "animation: shimmer 1.5s linear infinite; background-size: 200% 100%;" if v_clean == "processing" else ""
    
    return f"""
    <div style='
        background: {style["bg"]}; 
        border: 1.5px solid {style["border"]}; 
        border-radius: 18px; 
        padding: 28px; 
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35), 0 0 20px {glow_color}22;
        backdrop-filter: blur(12px);
        animation: fadeInUp 0.4s ease-out;
        position: relative;
        overflow: hidden;
    '>
        <!-- Emoji with glow -->
        <div style='font-size: 44px; filter: drop-shadow(0 0 12px {glow_color}); margin-bottom: 8px;'>{style["emoji"]}</div>
        
        <!-- Verdict Text -->
        <div style='font-size: 22px; font-weight: 800; color: {style["text"]}; letter-spacing: 1.5px; text-transform: uppercase;'>{safe_verdict}</div>
        
        <!-- Confidence Bar -->
        <div style='margin-top: 16px; padding: 0 20px;'>
            <div style='
                height: 8px; border-radius: 4px; 
                background: rgba(15, 23, 42, 0.6); 
                overflow: hidden;
                box-shadow: inset 0 1px 3px rgba(0,0,0,0.3);
            '>
                <div style='
                    height: 100%; width: {bar_width}%; border-radius: 4px;
                    background: {style["bar_color"]};
                    transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
                    {bar_extra}
                '></div>
            </div>
            <div style='font-size: 13px; color: {style["text"]}; margin-top: 8px; font-weight: 600;'>
                Confidence: <span style='color: #f1f5f9; font-weight: 700;'>{confidence:.1f}%</span>
            </div>
        </div>
    </div>
    """
