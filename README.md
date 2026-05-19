# AQuA Intelligence Platform

An AI-powered requirements analysis platform with a multi-engine pipeline, corporate Knowledge Layer, and automated quality artifact generation.

---

## Overview

The AQuA Intelligence Platform transforms software requirements into structured, traceable, and actionable analyses. Each requirement runs through a specialized engine pipeline that identifies ambiguities, risks, gaps, and business rules — then automatically generates test scenarios, RTM, and ready-to-use artifacts.

```
Input (Requirement)
  → Normalizer           (structuring + corporate context)
  → [Parallel Engines]   (Ambiguity + Risk + Rules + Gap + Coverage + Inference)
  → Knowledge Aggregator (institutional memory)
  → Traceability Engine  (RTM + scenarios + test cases)
  → Synthesis Engine     (cross-engine correlation)
  → Auto-enrichment KB   (automatic learning)
  → Response             (saved, versioned, traceable)
  → Artifact Generation  (on-demand, 9 artifacts, 4 profiles)
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Database | SQLite (SQLAlchemy) |
| AI | Azure OpenAI / Gemini / Anthropic (pluggable) |
| Frontend | HTML + CSS + JS (no framework) |
| Semantic Search | TF-IDF (no embeddings, fully offline) |

---

## Project Structure

```
backend/
├── main.py                        # FastAPI app + endpoints
├── orchestrator.py                # Pipeline coordinator
├── seed_knowledge.py              # Initial KB seed
├── .env                           # Configuration (not committed)
├── requirements.txt
│
├── engines/
│   ├── normalizer.py              # Stage 1: normalization + RN/CA parser
│   ├── ambiguity.py               # Ambiguity detection
│   ├── risk.py                    # Risk analysis
│   ├── rules.py                   # Business rule extraction
│   ├── gap.py                     # Gap identification
│   ├── coverage.py                # Coverage validation
│   ├── requirements_inference.py  # Implicit RF and RNF inference
│   ├── knowledge_aggregator.py    # Historical memory aggregation
│   ├── knowledge_enricher.py      # KB auto-enrichment
│   ├── traceability.py            # RTM + scenarios + test cases (v2)
│   └── artifact_generator.py     # Artifact generation (v2)
│
├── models/
│   ├── schemas.py                 # Pydantic models
│   └── database.py                # SQLAlchemy + helpers
│
├── providers/
│   ├── base.py                    # Base interface
│   ├── b3gpt.py                   # Azure OpenAI (corporate)
│   ├── anthropic.py               # Anthropic Claude
│   ├── gemini.py                  # Google Gemini
│   └── factory.py                 # Provider resolver
│
├── repositories/
│   ├── analysis.py                # Analysis CRUD
│   ├── project.py                 # Project CRUD
│   ├── knowledge.py               # Knowledge Base CRUD
│   ├── story_links.py             # Story relationship links
│   └── defects.py                 # Defect management
│
└── utils/
    ├── config.py                  # Settings (pydantic-settings)
    ├── id_detector.py             # Story ID detection (BSAG-1724)
    ├── knowledge_context.py       # Semantic context for engines
    ├── requirement_parser.py      # Structured RN/CA parser
    ├── semantic_search.py         # TF-IDF search
    ├── version_delta.py           # Version delta analysis
    └── parser.py                  # JSON extraction helpers

frontend/
├── index.html                     # Main hub
└── story.html                     # Story management
```

---

## Setup

### .env

```env
# AI Provider
AI_PROVIDER=b3gpt           # b3gpt | anthropic | gemini
AI_MODEL=<model-name>
AI_API_KEY=<your-token>
BASE_URL=<your-corporate-endpoint>

# Application
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

# Pipeline
ENGINE_MAX_TOKENS=8000
ENGINE_TIMEOUT=120
ENGINE_CONCURRENCY=5
ENGINE_LANGUAGE=portuguese

# Database
DB_PATH=qa_system.db
```

### Available Providers

| Provider | AI_PROVIDER | Endpoint pattern |
|----------|-------------|-----------------|
| Azure OpenAI (corporate) | `b3gpt` | `{BASE_URL}/deployments/{model}/chat/completions` |
| Anthropic | `anthropic` | api.anthropic.com |
| Google Gemini | `gemini` | generativelanguage.googleapis.com |

---

## Installation

```powershell
# 1. Install dependencies
py -3.12 -m pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env
# Edit .env with your values

# 3. Initialize database and seed
py -3.12 seed_knowledge.py

# 4. Start server
py -3.12 -m uvicorn main:app --reload
```

Open `frontend/index.html` in your browser.

---

## Analysis Pipeline

### Parallel Engines (Stage 2)

| Engine | What it does |
|--------|-------------|
| **Normalizer** | Structures the requirement, extracts RNs and CAs via parser, injects KB context |
| **Ambiguity** | Identifies subjective terms, missing conditions, inconsistencies |
| **Risk** | Classifies functional, security, regulatory and technical risks |
| **Rules** | Extracts explicit and implicit business rules |
| **Gap** | Detects missing scenarios, dependencies and absent requirements |
| **Coverage** | Validates acceptance criteria and flow coverage |
| **Inference** | Infers implicit FRs and NFRs from RNs, CAs, risks and domain |

### Knowledge Layer 3c

```
TF-IDF semantic search     → finds by meaning, not just keyword match
Automatic enrichment       → each analysis enriches the KB
Specialized context        → Risk Engine gets risk history, Gap gets gaps
Confidence scoring         → pattern seen 8x = 90% confidence
Version delta              → detects what changed between v1 and v6
Impact propagation         → identifies test cases affected by changes
```

### Traceability Engine v2

Generates a complete RTM from RNs and CAs extracted by the parser:

```
| Test ID | RN    | CA    | Test Case Title          | Risk  | Gap | Priority | Automated |
|---------|-------|-------|--------------------------|-------|-----|----------|-----------|
| CT-001  | RN-01 | CA-01 | Card display on Home     | —     | —   | high     | ✓         |
| CT-005  | RN-05 | CA-06 | Access denied via URL    | RSK-3 | —   | critical | ✓         |
```

- Mandatory positive and negative scenarios
- Every risk finding → negative test case
- `rn_descriptions` and `ca_descriptions` with exact text from requirement

### Artifact Generation v2

9 artifacts across 4 profiles using real pipeline context:

```
QA
├── Gherkin / BDD          → scenarios with @RN-XX @CA-XX @RSK-XXX tags
├── Detailed Test Cases    → CT-XXX - RN-XX | CA-XX: title
└── Evidence Template      → execution table per real CT

Dev
├── Automation Skeletons   → RF + Playwright + pytest
└── Technical Gap Analysis → impact by layer

PO
├── Acceptance Criteria    → existing CAs + new ones from gaps
├── Functional Gap Analysis→ what the user won't be able to do
└── Business Value         → value, risks and KPIs in business language

Audit
├── Risk Report            → real findings with historical correlation
└── Exportable RTM         → full format for audit
```

---

## API Reference

```
POST /api/v1/analyze
POST /api/v1/analyze/quick
GET  /api/v1/health
GET  /api/v1/history                    ?limit=N&project_id=X
GET  /api/v1/history/{id}
GET  /api/v1/stories/{id}/history
GET  /api/v1/stories/{id}/family
GET  /api/v1/stories/{id}/knowledge
GET  /api/v1/stories/{id}/defects
GET  /api/v1/stories/{id}/delta        ?v_from=1&v_to=2
GET  /api/v1/stories/{id}/impact
GET  /api/v1/stories/{id}/versions
POST /api/v1/artifacts/generate        {analysis_id, profiles?}
GET  /api/v1/artifacts/{analysis_id}
GET  /api/v1/knowledge                  ?project_id&category
POST /api/v1/knowledge
GET  /api/v1/knowledge/stats
POST /api/v1/knowledge/search/semantic
GET  /api/v1/projects
POST /api/v1/projects
```

---

## Frontend

### Hub (`index.html`)

- Pipeline flow bar with real-time scores
- 5 modules: QA Reasoning · Knowledge Layer · Traceability · Coverage · Artifact Generation
- Synthesis Engine card with cross-engine correlations
- Requirements Inference card (implicit FRs and NFRs)
- History panel with real-time search
- Auto-detection of story ID for navigation to story.html
- Responsive layout: ultrawide 29" → mobile 480px
- Full WCAG 2.1 AA compliance

### Story Page (`story.html`)

7 tabs per story:

| Tab | Content |
|-----|---------|
| **Versions** | Timeline with score delta, 🔍 View button (expands analysis) |
| **Defects** | CRUD with Jira ID, severity, type, inline status |
| **Links** | Story family, parent/child relationships |
| **RTM** | Scenarios, test cases and traceability matrix |
| **RF/RNF** | Inferred functional and non-functional requirements |
| **Artifacts** | Per-profile generation, per-artifact download |
| **Knowledge** | KB entries with `auto` badge and confidence % |

---

## Roadmap

```
✅ SQLite persistence
✅ Incremental versioning by story ID
✅ Knowledge Layer
   ✅ Connected to pipeline
   ✅ Story/ID linking (defects, family, improvements)
   ✅ Intelligent memory (semantic, delta, impact)
✅ Traceability Engine v2 (AI-powered)
✅ Artifact Generation v2 (context-driven)
✅ Requirements Inference Engine
✅ Corporate provider (Azure OpenAI)
✅ Ultrawide layout + WCAG 2.1 AA

⬜ Deploy (Railway / Render / Azure)
⬜ Corporate authentication (SSO / OAuth)
⬜ Knowledge Layer — vector embeddings
⬜ Traceability — contradiction detection between RNs
⬜ Xray / Jira export
```

---

## Troubleshooting

**Circular import in engines**
→ Keep `engines/__init__.py` empty. Import via `import engines.X as X_mod`.

**Pydantic JSON serialization**
→ Use `model.model_dump(mode='json')` — never `model.model_dump()`.

**Insufficient tokens for large stories**
→ Increase `ENGINE_MAX_TOKENS=8000` in `.env`.

**Corrupted database after schema change**
→ Delete `qa_system.db` and run `py -3.12 seed_knowledge.py` again.

---

## Design Decisions

**Why SQLite?**
Zero configuration, works offline, sufficient for internal corporate use with moderate volume. Migration to PostgreSQL is trivial — just change the connection string.

**Why TF-IDF instead of embeddings?**
Works offline, zero cost, zero external API latency, sufficient for bases up to ~10k entries. Vector embeddings are on the roadmap for larger scale.

**Why a pluggable provider?**
The system has no dependency on any specific LLM. Switching from Gemini to Azure OpenAI is just 3 lines in `.env` and a restart.
