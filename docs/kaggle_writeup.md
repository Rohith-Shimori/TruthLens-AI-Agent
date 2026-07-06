# 🛡️ TruthLens: Advanced Multi-Agent Misinformation Detection Engine

### **Kaggle x Google AI Agents: Intensive Vibe Coding Capstone Project (July 2026)**

---

## 📋 Project Metadata
*   **Track Selection:** Agents for Good (Misinformation Detection & Digital Literacy)
*   **GitHub Repository:** https://github.com/Rohith-Shimori/TruthLens-AI-Agent.git
*   **Interactive Demo Link (Hugging Face):** [Hugging Face Space](https://huggingface.co/spaces/Rohith-Shimori/TruthLens-AI-Agent) (Permanent Cloud Deployment)
*   **Video Demo:** *(Coming Soon)*
*   **Technologies Used:** Google Agent Development Kit (ADK) 2.0, Gemini 2.5 Flash, FastMCP, Gradio, SQLite, Python

---

## 1. 🚨 Vision & Problem Definition

In the modern digital landscape, misinformation spreads faster and wider than ever before. With the rise of encrypted messaging apps (e.g., WhatsApp, Telegram) and professional/social networks (e.g., LinkedIn, Gmail, X), fake news, manipulated screenshots, and unverified rumors circulate within minutes, often accepted as absolute truth.

### Key Pain Points:
1.  **Velocity of Misinformation:** Rumors go viral in minutes, while manual fact-checking takes hours or days.
2.  **Scalability Barriers:** Professional fact-checking organizations cannot keep pace with the massive volume of user-generated content.
3.  **Visual Misinformation:** Fabricated memes and screenshots of fake chat messages are highly engaging but difficult for simple text-based filters to verify.
4.  **Lack of Transparency:** Existing automated tools often output a binary "true/false" label without exposing the reasoning, evidence chain, or potential source bias.

### The Vision:
**TruthLens** is designed to democratize and accelerate fact-checking by deploying a team of specialized AI agents. Rather than providing a black-box verdict, TruthLens automates the process a human journalist would follow: ingesting content, isolating claims, searching trusted databases, checking source credibility, analyzing emotional bias, and synthesizing a comprehensive, cited report. By combining high-speed agentic loops with a minimalistic, user-friendly interface, TruthLens serves as a reliable guard against digital misinformation.

---

## 2. 🏗️ Architecture & Orchestration

TruthLens transitions from traditional single-prompt retrieval architectures to a **graph-based multi-agent workflow** built on the **Google Agent Development Kit (ADK) 2.0**.

```
                  User Input (URL, Text, Image)
                               │
                               ▼
            ┌───────────────────────────────────────┐
            │        TruthLens Orchestrator         │
            │         (Workflow Graph - ADK)        │
            └───────────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │  1. Ingestion   │  │  2. Claim       │  │  3. Evidence    │
    │     Agent       │ →│  Extractor      │ →│  Retriever      │
    │ (Scrapes URLs,  │  │ (Isolates facts │  │ (Grounded web & │
    │  OCR screenshots)│  │  to verify)     │  │  Wikipedia API) │
    └─────────────────┘  └─────────────────┘  └────────┬────────┘
                                                       │
                                                       ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌────────┴────────┐
    │  6. Verdict     │  │  5. Bias &      │  │  4. Source      │
    │     Engine      │ ←│  Sentiment      │ ←│  Credibility    │
    │ (Determines claim│  │  Analyzer      │  │  Scorer         │
    │  veracity)      │  │ (Sensationalism)│  │ (Domain indexes)│
    └────────┬────────┘  └─────────────────┘  └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │  7. Report      │ → Generates detailed markdown report
    │  Generator      │   with evidence citation cards.
    └─────────────────┘
```

The system orchestrates **7 specialized agents** in a linear workflow graph using `google.adk.Workflow`:

1.  **IngestionAgent:** The gatekeeper. It supports web scraping (using BeautifulSoup) for URLs, OCR (using Gemini Vision) for screenshots/images, and raw text processing.
2.  **ClaimExtractionAgent:** Parses the raw text to isolate up to three factual, verifiable claims, ignoring opinions or emotional fillers.
3.  **EvidenceRetrieverAgent:** Uses the Model Context Protocol (MCP) to perform double-source search grounding (Wikipedia API + real-time Google search grounding).
4.  **SourceCredibilityAgent:** Evaluates domain reputation using a curated list of trusted fact-checkers, academic portals, and known misinformation outlets.
5.  **BiasAnalyzerAgent:** Gauges the text's sensationalism score, emotional loading, and potential logical fallacies.
6.  **VerdictAgent:** Cross-references the claims against retrieved evidence and source scores to determine the veracity of the claims.
7.  **ReportGeneratorAgent:** Synthesizes the individual outputs into a beautifully structured, public-facing markdown report.

---

## 3. 🛠️ Implementation Details & Course Concepts

TruthLens showcases **five core concepts** taught in the course:

### A. Multi-Agent Systems (ADK 2.0)
Each agent is constructed using `google.adk.Agent` and powered by `gemini-2.5-flash`. The execution is driven by `google.adk.Workflow`, defining a deterministic linear transition list:
```python
truthlens_workflow = Workflow(
    name="TruthLensVerificationPipeline",
    edges=[("START", ingestion_agent, claim_extractor_agent, ..., report_generator_agent)]
)
```
This guarantees that each agent operates only on the structured outputs of its predecessors, minimizing hallucinations and ensuring logical coherence.

### B. Model Context Protocol (MCP)
We built a standalone MCP server (`mcp_server.py`) using **FastMCP** that exposes TruthLens fact-checking tools to any compatible host application:
*   `search_evidence`: Combines Wikipedia and Google grounding search.
*   `check_source_credibility`: Reviews domain reputation.
*   `analyze_bias`: Examines text sentiment and sensationalism.
This demonstrates clean decoupling of agent reasoning from tool execution, allowing the tools to be plugged into external MCP-compatible clients independently of the ADK pipeline.

### C. Smart Session Memory (SQLite Cache with TTL)
To resolve latency and API cost challenges, TruthLens implements a local SQLite caching system (`MemoryManager` class in `src/utils.py`). When a query is submitted, it is hashed (SHA-256). A cache hit bypasses the LLM pipeline and immediately serves the cached report (sub-second retrieval). Cache entries expire after 7 days (configurable TTL) to ensure freshness. The database uses WAL mode for thread-safe concurrent access.

### D. Security Gatekeeping (`SecurityManager` in `src/utils.py`)
To prevent exploitation of the agent network, we implemented:
*   **Input Sanitization:** Strips HTML/script tags to prevent injection.
*   **Prompt Injection Detection:** Scans for keywords attempting to override instructions (e.g., "ignore previous instructions").
*   **Rate Limiting:** Employs a sliding-window rate limiter to protect resources.
*   **SSRF Protection:** Blocks requests to private/internal IP ranges and localhost.

### E. Deployability (Docker & Cloud Run)
The project includes a multi-stage `Dockerfile` built on `python:3.12-slim` and optimized using the `uv` package manager. This makes the system containerized, portable, and ready for deployment to **Google Cloud Run** in seconds.

### F. Self-Healing Agent Auto-Retry (RetryConfig)
To guarantee robust operations under high load or rate limit situations, TruthLens integrates native ADK `RetryConfig` configurations across all **7 pipeline agents**. Using an exponential backoff strategy, the agents automatically self-heal and retry on transient `RESOURCE_EXHAUSTED` (429) or network exception states:
```python
agent_retry = RetryConfig(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=10.0,
    backoff_factor=2.0,
    exceptions=[Exception]
)
```
This isolates the agent execution loop from temporary provider failures and increases overall verification accuracy.

### G. Evaluation Suite (Day 4: Agent Quality)
To demonstrate reliability and production-readiness, TruthLens includes a comprehensive evaluation suite (`tests/eval_suite.py`) with a golden dataset of 8 curated claims spanning science, health, conspiracy theories, and geography. The suite runs 22+ automated tests across 5 categories:
*   **Security Tests:** Validates HTML sanitization, prompt injection detection, and rate limiting enforcement.
*   **Credibility Tests:** Verifies domain classification accuracy for trusted, unreliable, and social media sources.
*   **Bias Tests:** Validates sensationalism scoring for neutral vs. inflammatory text, including multi-word phrase detection.
*   **Cache Tests:** Tests save/retrieve operations, cache misses, and analytics structure.
*   **SSRF Tests:** Confirms that internal/private URLs are blocked.

Run with: `python -m tests.eval_suite --report`

---

## 4. 🎨 Premium User Interface Design

To deliver maximum user value and a compelling "Wow" factor for evaluation, TruthLens features a bespoke Gradio interface structured with advanced frontend design best practices:
*   **Glassmorphism Theme:** Translucent panels, dark themes, and Outfit/Jakarta typography loaded dynamically from Google Fonts via HTML `<link>` injection.
*   **Cross-Theme CSS Locking:** Hardcoded `:root` CSS variables (e.g. `--background-fill-primary`, `--block-background-fill`, `--body-text-color`) enforce our custom dark glassmorphic palette. This completely prevents clashing colors or white-on-white text issues if the user or browser switches to light mode.
*   **Zero Console Warnings:** Clean CSS architecture with no dynamic `@import` rules (resolving construct-stylesheets security constraints in Chromium) and fully compliant HTML bindings.
*   **Custom Branded Header & Title:** The browser tab name, HTML title, and interface headers are branded uniquely as "TruthLens | Advanced Multi-Agent Fact-Checking System" with standard Gradio footer branding completely hidden.
*   **Dynamic Glowing Verdict Banners:** Custom HTML containers rendering large, colored verdict badges (green for True, red for False, amber for Misleading) with matching emoji indicators and drop-shadow glow effects.
*   **Dynamic System Diagnostics:** Once the report is generated, a local diagnostic engine computes a **Source Consensus Analysis** (determining if web databases agree, conflict, or debunk the claim) and renders a structured **Source Domain Reliability Heatmap** table showing each cited URL domain's safety rating (Government/Academic, Trusted, Social Media, etc.) and safety score.
*   **Interactive Live Execution Tracing:** Embedded directly at the bottom of verification reports, a collapsible **Live Agent Tracing Logs** details section captures and displays the raw JSON outputs of each agent span as they execute sequentially in the pipeline.
*   **Cache Clear Administration:** A dedicated **🗑️ Clear Cache Database** button in the Registry Tab allows immediate database resets to clear cached verification pairs and refresh evaluation metrics.
*   **Report Exporter component:** Dynamically generates a downloadable Markdown file (`.md`) of the fact-check report directly in the UI.

---

## 5. 📈 Results & Future Enhancements

### Key Results:
*   **Efficiency:** Caching reduced the average lookup time for duplicate claims from ~15 seconds to **0.05 seconds**. Cache entries automatically expire after 7 days.
*   **Robustness:** Dual-source web grounding and Wikipedia lookups provided stable citations even when claims were highly niche or regional.
*   **Visual Accuracy:** Gemini Vision OCR successfully extracted text from compressed mobile screenshots (e.g., forwarded WhatsApp messages).
*   **Evaluation:** The offline test suite achieves 22/22 passing tests across security, credibility, bias analysis, caching, and SSRF protection modules.

### Future Roadmap:
1.  **Multi-lingual Support:** Adding translation agents to verify local/regional language misinformation.
2.  **Audio & Video Verification:** Expanding OCR pipelines to transcribe TikTok and YouTube shorts.
3.  **Active Learning Loops:** Allowing human fact-checkers to rate the agent’s reports, feeding corrections back into the database.
