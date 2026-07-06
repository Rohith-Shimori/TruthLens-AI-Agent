import gradio as gr

# Default report placeholder (Premium Landing Intro)
WELCOME_MESSAGE = """
# 🛡️ TruthLens Fact-Checking Report

### Enter a factual claim to retrieve evidence from trusted sources.

TruthLens leverages a network of 7 specialized AI agents to analyze content credibility, bias, and consensus. 
To begin, paste a claim in the input field, upload a screenshot of a forwarded message, or pick one of the sample claims below.
"""

# Custom CSS for Outfit/Plus Jakarta typography, glassmorphism panels, and button glows
custom_css = """
/* Enforce dark-theme CSS variables in both light and dark mode */
:root, .dark {
    --background-fill-primary: #0b0f19 !important;
    --background-fill-secondary: #0f172a !important;
    --block-background-fill: rgba(21, 28, 44, 0.65) !important;
    --block-border-color: #1e293b !important;
    --block-border-width: 1px !important;
    
    /* Text Colors */
    --body-text-color: #cbd5e1 !important;
    --body-text-color-subdued: #94a3b8 !important;
    --block-title-text-color: #f8fafc !important;
    --block-label-text-color: #94a3b8 !important;
    --input-text-color: #f8fafc !important;
    --input-placeholder-color: #475569 !important;
    
    /* Input Elements */
    --input-background-fill: rgba(15, 23, 42, 0.8) !important;
    --input-border-color: #1e293b !important;
    --input-border-width: 1px !important;
    
    /* Buttons */
    --button-primary-background-fill: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    --button-primary-background-fill-hover: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    --button-primary-text-color: white !important;
    --button-secondary-background-fill: rgba(30, 41, 59, 0.4) !important;
    --button-secondary-background-fill-hover: rgba(59, 130, 246, 0.1) !important;
    --button-secondary-text-color: #94a3b8 !important;
    --button-secondary-border-color: #1e293b !important;
    
    /* Tables */
    --table-border-color: #1e293b !important;
    --table-header-background-fill: rgba(30, 41, 59, 0.6) !important;
    --table-row-background-fill: rgba(15, 23, 42, 0.4) !important;
}

* {
    font-family: 'Plus Jakarta Sans', 'Outfit', sans-serif !important;
}

body {
    background-color: #0b0f19 !important;
    color: #cbd5e1 !important;
}

.gradio-container {
    max-width: 1100px !important;
    margin: 0 auto !important;
    padding-top: 40px !important;
    background-color: #0b0f19 !important;
}

/* Hide built-with Gradio footer branding completely */
footer {
    display: none !important;
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

/* Force markdown rendering colors to behave under light mode settings */
.prose p, .prose li, .prose span, .prose ul, .prose ol, .prose strong {
    color: #cbd5e1 !important;
}

.prose h1, .prose h2, .prose h3, .prose h4, .prose h5, .prose h6 {
    color: #f8fafc !important;
    font-weight: 700 !important;
}

.prose blockquote {
    border-left-color: #3b82f6 !important;
    color: #94a3b8 !important;
    background: rgba(30, 41, 59, 0.2) !important;
}

.prose code {
    color: #60a5fa !important;
    background: rgba(15, 23, 42, 0.6) !important;
}

/* Custom styles for download File component to blend with glassmorphism */
.file-preview {
    background: rgba(15, 23, 42, 0.8) !important;
    border: 1px solid #3b82f6 !important;
    border-radius: 12px !important;
}
"""

def get_verdict_html(verdict: str, confidence: float) -> str:
    """Returns a customized premium HTML container for the verdict badge and confidence slider."""
    v_clean = verdict.strip().lower()
    
    # Custom badge configurations
    verdict_styles = {
        "true": {
            "emoji": "✅",
            "bg": "rgba(16, 185, 129, 0.15)",
            "border": "#10b981",
            "text": "#10b981",
            "glow": "#10b981"
        },
        "mostly true": {
            "emoji": "✓",
            "bg": "rgba(52, 211, 153, 0.15)",
            "border": "#34d399",
            "text": "#34d399",
            "glow": "#34d399"
        },
        "misleading": {
            "emoji": "⚠️",
            "bg": "rgba(245, 158, 11, 0.15)",
            "border": "#f59e0b",
            "text": "#f59e0b",
            "glow": "#f59e0b"
        },
        "false": {
            "emoji": "❌",
            "bg": "rgba(239, 68, 68, 0.15)",
            "border": "#ef4444",
            "text": "#ef4444",
            "glow": "#ef4444"
        },
        "unverified": {
            "emoji": "🔍",
            "bg": "rgba(100, 116, 139, 0.15)",
            "border": "#64748b",
            "text": "#94a3b8",
            "glow": "#64748b"
        },
        "processing": {
            "emoji": "⚡",
            "bg": "rgba(59, 130, 246, 0.15)",
            "border": "#3b82f6",
            "text": "#3b82f6",
            "glow": "#3b82f6"
        }
    }
    
    # Fallback to general style if verdict is unknown
    style = verdict_styles.get(v_clean, verdict_styles["unverified"])
    glow_color = style["glow"]
    
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
