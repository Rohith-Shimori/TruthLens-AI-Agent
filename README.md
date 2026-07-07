# 🛡️ TruthLens: Advanced Multi-Agent Misinformation Detection Engine

<p align="center">
  <img src="assets/logo.png" width="140" alt="TruthLens Logo">
</p>

<p align="center">
  <strong>Kaggle × Google AI Agents: Intensive Vibe Coding Capstone Project</strong><br>
  <em>AI-Powered Multi-Agent Misinformation Detection for Modern Digital Platforms</em>
</p>

<p align="center">
  <a href="https://huggingface.co/spaces/Rohith-Shimori/TruthLens-AI-Agent"><img src="https://img.shields.io/badge/🤗%20Demo-Hugging%20Face-blue" alt="HF Space"></a>
  <a href="https://youtu.be/o_uXlLCLFfg"><img src="https://img.shields.io/badge/💽%20Demo-YouTube-red" alt="HF Space"></a>
  <a href="docs/kaggle_writeup.md"><img src="https://img.shields.io/badge/📝-Competition%20Writeup-green" alt="Writeup"></a>
  <img src="https://img.shields.io/badge/Tests-24%2F24%20Passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/Agents-7%20Specialized-purple" alt="Agents">
  <img src="https://img.shields.io/badge/ADK-2.0-orange" alt="ADK">
</p>

---

## 🎯 What is TruthLens?

TruthLens is an enterprise-grade, multi-agent fact-checking system designed to help users verify claims spreading across social media (WhatsApp, Telegram, Twitter, LinkedIn). It orchestrates **7 specialized AI agents** through a deterministic pipeline to analyze content credibility, bias, and consensus.

**Built with:** Google Agent Development Kit (ADK) 2.0 · Gemini 2.5 Flash · FastMCP · Gradio · SQLite

### ✨ Key Highlights
| Feature | Description |
|---------|-------------|
| 🤖 **7 Agent Pipeline** | ClaimExtractor → EvidenceHunter → FactChecker → CredibilityAnalyzer → BiasAnalyzer → VerdictAgent → ReportGenerator |
| 🔗 **MCP Protocol** | Standalone FastMCP server exposing tools to any compatible host |
| 🖼️ **Multimodal OCR** | Verify WhatsApp/Telegram screenshots via Gemini Vision |
| 🛡️ **Security Stack** | SSRF protection, XSS escaping, prompt injection detection, rate limiting |
| 💾 **Smart Caching** | SQLite with SHA-256 hashing, 7-day TTL, WAL mode for thread safety |
| ✅ **Evaluation Suite** | 24 automated tests across 5 categories — 100% pass rate |
| 📊 **Structured Logging** | Production-grade logging across all modules |

---

## 🏗️ System Architecture

TruthLens employs a sequential multi-agent graph containing 7 specialized agents:

```
📥 Input → 🔍 ClaimExtractor → 🌐 EvidenceHunter → ✅ FactChecker → ⚖️ BiasAnalyzer → 📊 Verdict → 📝 Report
```

<p align="center">
  <img src="assets/architecture.png" width="650" alt="TruthLens Multi-Agent Architecture">
</p>

---

## 📸 Screenshots

<p align="center">
  <b>🔍 Verification Hub — Premium Dark Glassmorphism UI</b><br>
  <img src="assets/screenshots/home.png" width="800" alt="TruthLens Verification Hub"><br><br>
  <b>📊 TruthLens Registry — System Metrics & Cache</b><br>
  <img src="assets/screenshots/registry.png" width="800" alt="TruthLens Registry Dashboard"><br><br>
  <b>🔌 Developer API — Integration Documentation</b><br>
  <img src="assets/screenshots/developer_api.png" width="800" alt="TruthLens Developer API">
</p>

---

## 📚 Course Concepts Demonstrated

| Day | Concept | Implementation |
|:---:|---------|----------------|
| 1 | **Foundational Models** | Gemini 2.5 Flash for reasoning, OCR, and evidence synthesis |
| 2 | **Agents & Tools** | 7 ADK agents with custom Python tools + MCP server (`mcp_server.py`) |
| 3 | **Multi-Agent Systems** | Sequential `Workflow` graph with structured inter-agent communication |
| 4 | **Agent Quality** | 24-test evaluation suite, golden dataset, structured logging |
| 5 | **Deployment** | HuggingFace Space + Docker + Cloud Run ready |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- A Google Gemini API Key ([Get one here](https://aistudio.google.com/))

### Installation
```bash
# Clone the repository
git clone https://github.com/Rohith-Shimori/TruthLens-AI-Agent.git
cd TruthLens-AI-Agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Running
```bash
# Start the web UI
python app.py
# Open http://127.0.0.1:7860

# Run the evaluation suite
python -m tests.eval_suite --report

# Start the MCP server
python mcp_server.py
```

---

## 🐳 Docker Deployment
```bash
docker build -t truthlens .
docker run -p 7860:7860 --env-file .env truthlens
```

---

## 📊 Evaluation Results

```
======================================================================
🛡️  TruthLens Evaluation Suite — Golden Dataset Testing
======================================================================
📋 Security Manager:     6/6  ✅
📋 Credibility Scorer:   7/7  ✅
📋 Bias Analyzer:        4/4  ✅
📋 Memory Cache:         4/4  ✅
📋 SSRF Protection:      3/3  ✅
──────────────────────────────
📊 RESULTS: 24/24 tests passed (100.0% accuracy)
======================================================================
```

---

## 📁 Project Structure

```
TruthLens-AI-Agent/
├── app.py                  # Main Gradio application (800+ lines)
├── mcp_server.py           # FastMCP server for tool interoperability
├── requirements.txt        # Pinned dependencies
├── Dockerfile              # Multi-stage Docker build
├── watchdog.py             # HA deployment watchdog
├── src/
│   ├── pipeline.py         # ADK Workflow with 7 agents
│   ├── retrieval.py        # Web scraping, Wikipedia, Google Grounding
│   ├── inference.py        # Model config, retry policies, rate limiting
│   ├── utils.py            # SecurityManager, MemoryManager, BiasAnalyzer
│   └── ui.py               # Premium CSS, verdict cards, HTML templates
├── tests/
│   ├── eval_suite.py       # 24-test evaluation suite with golden dataset
│   └── eval_report.json    # Latest evaluation results
├── data/
│   └── sample_claims.json  # 8 curated sample claims
├── docs/
│   └── kaggle_writeup.md   # Competition writeup
└── assets/
    ├── logo.png
    ├── architecture.png
    └── screenshots/
        ├── home.png
        ├── registry.png
        └── developer_api.png
```

---

## ⚠️ Limitations
1. **Gemini Free-Tier Quota:** High load may trigger `RESOURCE_EXHAUSTED` (429). Handled via ADK `RetryConfig` with exponential backoff.
2. **Visual Language Context:** OCR works best on English text screenshots. Highly distorted or handwritten regional text may reduce accuracy.
3. **Real-Time Data Lag:** Breaking news within the last few minutes may have slight retrieval delay.

---

## 🗺️ Future Roadmap
1. 🌍 **Multi-Lingual Verification** — Translation agents for regional language claims
2. 🎥 **Audio & Video Transcription** — Whisper-based transcription for TikTok/Reels/Shorts
3. 🔄 **Self-Correction Loop** — LoopAgent for automated report quality validation
4. 👥 **RLHF Integration** — Professional fact-checker feedback to improve agent prompts

---

<p align="center">
  <strong>© 2026 TruthLens • Kaggle × Google AI Agents Capstone</strong><br>
  <em>Built with ❤️ using Google ADK 2.0 & Gemini 2.5 Flash</em>
</p>
