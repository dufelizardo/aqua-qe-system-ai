# QA Intelligence System — Backend

Multi-engine QA analysis pipeline with hybrid parallelism.

```
Input → Normalizer → [Ambiguity + Risk + Rules + Gap + Coverage] → Synthesis → Response
```

## Stack
- **Python 3.12** + **FastAPI** + **Pydantic v2**
- **AI Providers**: Anthropic (Claude), OpenAI (GPT-4/o), Corporate proxy
- **Docker** for containerization

---

## Quick Start (local dev)

```bash
# 1. Clone and enter project
cd qa-system

# 2. Configure environment
cp .env.example .env
# Edit .env: set AI_PROVIDER, AI_API_KEY, AI_MODEL

# 3. Run with Docker
docker-compose up --build

# OR run directly
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 4. Test
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/docs   # Interactive API docs
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `corporate` |
| `AI_MODEL` | `claude-sonnet-4-20250514` | Model name for the provider |
| `AI_API_KEY` | — | Your API key |
| `AI_BASE_URL` | `None` | Corporate proxy URL (optional) |
| `ENGINE_MAX_TOKENS` | `1500` | Max tokens per engine call |
| `ENGINE_TIMEOUT` | `30` | Timeout per engine (seconds) |
| `ENGINE_CONCURRENCY` | `5` | Parallel engine limit |

---

## API Endpoints

### `POST /api/v1/analyze`
Full pipeline. Main endpoint for all frontends.

```json
{
  "requirement": "The user must be able to login with email and password",
  "context": "Optional: rules, bugs, historical context",
  "project_id": "PROJ-001",
  "engines": null
}
```

Response: full `AnalysisResponse` with all engine results + synthesis.

### `POST /api/v1/analyze/quick`
Normalizer only — fast structured preview.

### `GET /api/v1/health`
Provider connectivity status.

### `GET /api/v1/config`
Current provider/model info (no secrets exposed).

---

## Project Structure

```
backend/
├── main.py              # FastAPI app + routes
├── orchestrator.py      # Pipeline coordinator
├── engines/
│   ├── normalizer.py    # Stage 1: requirement parsing
│   ├── ambiguity.py     # Parallel: vague terms, missing specs
│   ├── risk.py          # Parallel: technical/security/business risks
│   ├── rules.py         # Parallel: business rules extraction
│   ├── gap.py           # Parallel: missing scenarios/coverage
│   ├── coverage.py      # Parallel: test coverage analysis
│   └── synthesis.py     # Stage 3: cross-engine correlations
├── providers/
│   ├── base.py          # Abstract interface
│   ├── anthropic.py     # Claude
│   ├── openai.py        # GPT-4/o (+ Azure)
│   ├── corporate.py     # Internal proxy (OpenAI-compatible)
│   └── factory.py       # Provider resolver
├── models/
│   └── schemas.py       # All Pydantic data contracts
└── utils/
    ├── config.py         # Settings (pydantic-settings)
    └── parser.py         # Safe JSON extraction from LLM output
```

---

## Switching AI Providers

Change only `.env` — zero code changes:

```bash
# Anthropic
AI_PROVIDER=anthropic
AI_MODEL=claude-sonnet-4-20250514
AI_API_KEY=sk-ant-...

# OpenAI
AI_PROVIDER=openai
AI_MODEL=gpt-4o
AI_API_KEY=sk-...

# Corporate proxy (OpenAI-compatible)
AI_PROVIDER=corporate
AI_MODEL=gpt-4o
AI_API_KEY=your-internal-key
AI_BASE_URL=https://ai-gateway.yourcompany.com/v1/chat/completions
```

---

## Deployment

### Railway / Render
- Connect GitHub repo
- Set env vars in dashboard
- Deploy — done.

### VPS / Kubernetes
```bash
docker build -t qa-system ./backend
docker run -p 8000:8000 --env-file .env qa-system
```

### Kubernetes secret for corporate key
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: qa-system-secrets
stringData:
  AI_API_KEY: "your-key"
  AI_BASE_URL: "https://your-proxy.com/v1/chat/completions"
```
