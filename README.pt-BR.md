# AQuA Intelligence Platform

Sistema inteligente de análise de requisitos orientado por IA, com pipeline multi-engine, Knowledge Layer corporativo e geração automatizada de artefatos de qualidade.

---

## Visão Geral

O AQuA Intelligence Platform transforma requisitos de software em análises estruturadas, rastreáveis e acionáveis. Cada requisito passa por um pipeline de engines especializadas que identificam ambiguidades, riscos, gaps, regras de negócio e geram automaticamente cenários de teste, RTM e artefatos prontos para uso.

```
Input (Requisito)
  → Normalizer           (estruturação + contexto corporativo)
  → [Parallel Engines]   (Ambiguity + Risk + Rules + Gap + Coverage + Inference)
  → Knowledge Aggregator (memória histórica institucional)
  → Traceability Engine  (RTM + cenários + casos de teste)
  → Synthesis Engine     (correlação cross-engine)
  → Auto-enrichment KB   (aprendizado automático)
  → Response             (salvo, versionado, rastreável)
  → Artifact Generation  (on-demand, 9 artefatos, 4 perfis)
```

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.12 + FastAPI |
| Banco de dados | SQLite (SQLAlchemy) |
| IA | Azure OpenAI / Gemini / Anthropic (plugável) |
| Frontend | HTML + CSS + JS (sem framework) |
| Busca semântica | TF-IDF (sem embeddings, offline) |

---

## Estrutura do Projeto

```
backend/
├── main.py                        # FastAPI app + endpoints
├── orchestrator.py                # Pipeline coordinator
├── seed_knowledge.py              # KB seed inicial
├── .env                           # Configuração (não commitado)
├── requirements.txt
│
├── engines/
│   ├── normalizer.py              # Stage 1: normalização + parser RN/CA
│   ├── ambiguity.py               # Detecção de ambiguidades
│   ├── risk.py                    # Análise de riscos
│   ├── rules.py                   # Extração de regras de negócio
│   ├── gap.py                     # Identificação de gaps
│   ├── coverage.py                # Validação de cobertura
│   ├── requirements_inference.py  # Inferência de RFs e RNFs implícitos
│   ├── knowledge_aggregator.py    # Agregação de memória histórica
│   ├── knowledge_enricher.py      # Auto-enriquecimento do KB
│   ├── traceability.py            # RTM + cenários + casos de teste (v2)
│   └── artifact_generator.py     # Geração de artefatos (v2)
│
├── models/
│   ├── schemas.py                 # Pydantic models
│   └── database.py                # SQLAlchemy + helpers
│
├── providers/
│   ├── base.py                    # Interface base
│   ├── b3gpt.py                   # Azure OpenAI (B3GPT corporativo)
│   ├── anthropic.py               # Anthropic Claude
│   ├── gemini.py                  # Google Gemini
│   └── factory.py                 # Provider resolver
│
├── repositories/
│   ├── analysis.py                # CRUD análises
│   ├── project.py                 # CRUD projetos
│   ├── knowledge.py               # CRUD Knowledge Base
│   ├── story_links.py             # Vínculos entre histórias
│   └── defects.py                 # Gestão de defeitos
│
└── utils/
    ├── config.py                  # Settings (pydantic-settings)
    ├── id_detector.py             # Detecção de IDs (BSAG-1724)
    ├── knowledge_context.py       # Contexto semântico para engines
    ├── requirement_parser.py      # Parser estruturado de RNs e CAs
    ├── semantic_search.py         # Busca TF-IDF
    ├── version_delta.py           # Delta entre versões
    └── parser.py                  # JSON extraction helpers

frontend/
├── index.html                     # Hub central
└── story.html                     # Gestão da história
```

---

## Configuração

### .env

```env
# Provider de IA
AI_PROVIDER=b3gpt           # b3gpt | anthropic | gemini
AI_MODEL=gpt4o-mini         # modelo disponível no provider
AI_API_KEY=<seu token>
BASE_URL=https://<sua-api-corporativa>/openai

# Aplicação
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

# Pipeline
ENGINE_MAX_TOKENS=8000
ENGINE_TIMEOUT=120
ENGINE_CONCURRENCY=5
ENGINE_LANGUAGE=portuguese

# Banco
DB_PATH=qa_system.db
```

### Providers disponíveis

| Provider | AI_PROVIDER | Endpoint |
|----------|-------------|----------|
| Azure OpenAI (corporativo) | `b3gpt` | `{BASE_URL}/deployments/{model}/chat/completions` |
| Anthropic | `anthropic` | api.anthropic.com |
| Google Gemini | `gemini` | generativelanguage.googleapis.com |

---

## Instalação e Execução

```powershell
# 1. Instalar dependências
py -3.12 -m pip install -r requirements.txt

# 2. Configurar .env (copiar e editar)
copy .env.example .env

# 3. Criar banco e seed inicial
py -3.12 seed_knowledge.py

# 4. Iniciar servidor
py -3.12 -m uvicorn main:app --reload
```

Acesse: `http://localhost:8000`
Frontend: abra `frontend/index.html` no navegador

---

## Pipeline de Análise

### Engines Paralelos (Stage 2)

| Engine | O que faz |
|--------|-----------|
| **Normalizer** | Estrutura o requisito, extrai RNs e CAs via parser, injeta contexto KB |
| **Ambiguity** | Identifica termos subjetivos, condições faltantes, inconsistências |
| **Risk** | Classifica riscos funcionais, de segurança, regulatórios e técnicos |
| **Rules** | Extrai regras de negócio explícitas e implícitas |
| **Gap** | Detecta cenários faltando, dependências e requisitos ausentes |
| **Coverage** | Valida cobertura de critérios de aceite e fluxos |
| **Inference** | Infere RFs e RNFs implícitos das RNs, CAs, riscos e domínio |

### Knowledge Layer 3c

```
Busca semântica TF-IDF       → encontra por significado, não só keyword
Alimentação automática        → cada análise enriquece o KB
Contexto especializado        → Risk Engine recebe riscos, Gap recebe gaps
Score de confiança            → padrão visto 8x = 90% confiança
Delta entre versões           → detecta o que mudou entre v1 e v6
Propagação de impacto         → identifica CTs afetados por mudanças
```

### Traceability Engine v2

Gera RTM completa a partir das RNs e CAs extraídas pelo parser:

```
| ID do Teste | RN    | CA    | Título do Caso de Teste | Risco | Gap | Prioridade | Automatizável |
|-------------|-------|-------|------------------------|-------|-----|------------|---------------|
| CT-001      | RN-01 | CA-01 | Exibição do card na Home| —     | —   | high       | ✓             |
| CT-005      | RN-05 | CA-06 | Acesso negado via URL   | RSK-3 | —   | critical   | ✓             |
```

- Cenários positivos e negativos obrigatórios
- Cada risco → CT negativo
- `rn_descriptions` e `ca_descriptions` com texto exato do requisito

### Artifact Generation v2

9 artefatos em 4 perfis usando contexto real do pipeline:

```
QA
├── Gherkin / BDD          → cenários com tags @RN-XX @CA-XX @RSK-XXX
├── Test Cases detalhados  → CT-XXX - RN-XX | CA-XX: título
└── Evidence Template      → tabela de execução por CT real

Dev
├── Automation Skeletons   → RF + Playwright + pytest
└── Gap Analysis técnico   → impacto por camada

PO
├── Critérios de Aceite    → CAs existentes + novos por gap
├── Gap Analysis funcional → o que o usuário não conseguirá fazer
└── Business Value         → valor, riscos e KPIs em linguagem de negócio

Auditoria
├── Risk Report            → findings reais com correlação histórica
└── RTM exportável         → formato completo para auditoria
```

---

## APIs

```
POST /api/v1/analyze                    # Análise completa
POST /api/v1/analyze/quick              # Análise rápida
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

### Hub Central (`index.html`)

- Pipeline flow bar com scores em tempo real
- 5 módulos: QA Reasoning · Knowledge Layer · Traceability · Coverage · Artifact Generation
- Synthesis Engine card com correlações cross-engine
- Requirements Inference card (RFs e RNFs implícitos)
- Painel histórico com busca em tempo real
- Navegação para story.html por ID detectado automaticamente
- Layout responsivo: ultrawide 29" → mobile 480px
- WCAG 2.1 AA completo

### Story Page (`story.html`)

7 abas por história:

| Aba | Conteúdo |
|-----|---------|
| **Versões** | Timeline com delta de scores, botão 🔍 Ver (expande análise) |
| **Defeitos** | CRUD com Jira ID, severidade, tipo, status inline |
| **Vínculos** | Família de histórias, parent/child |
| **RTM** | Cenários, casos de teste e matriz de rastreabilidade |
| **RF/RNF** | Requisitos funcionais e não-funcionais inferidos |
| **Artefatos** | Geração por perfil, download por artefato |
| **Conhecimento** | Entradas do KB com badge `auto` e % confiança |

---

## Roadmap

```
✅ 1. Persistência SQLite
✅ 2. Versionamento incremental por ID
✅ 3. Knowledge Layer
   ✅ 3a. Conectado ao pipeline
   ✅ 3b. Vinculação por história/ID
   ✅ 3c. Memória inteligente (semântica, delta, impacto)
✅ 4. Traceability Engine v2 (AI-powered)
✅ 5. Artifact Generation v2 (context-driven)
✅ 6. Requirements Inference Engine
✅ Provider B3GPT (Azure OpenAI corporativo)
✅ Layout ultrawide + WCAG 2.1 AA

⬜ Deploy (Railway / Render / Azure)
⬜ Autenticação corporativa (SSO / OAuth)
⬜ Knowledge Layer 3c — embeddings vetoriais
⬜ Traceability — detecção de contradições entre RNs
⬜ Exportação Xray / Jira
```

---

## Solução de Problemas

**Circular import nos engines**
→ Manter `engines/__init__.py` vazio. Importar via `import engines.X as X_mod`.

**JSON serialization (Pydantic)**
→ Usar `model.model_dump(mode='json')` — nunca `model.model_dump()`.

**Tokens insuficientes para histórias longas**
→ Aumentar `ENGINE_MAX_TOKENS=8000` no `.env`.

**Banco corrompido após mudança de schema**
→ Apagar `qa_system.db` e rodar `py -3.12 seed_knowledge.py` novamente.

---

## Arquitetura de Decisões

**Por que SQLite?**
Zero configuração, funciona offline, suficiente para uso corporativo interno com volume moderado. Migração para PostgreSQL é trivial — só trocar a connection string.

**Por que TF-IDF em vez de embeddings?**
Funciona offline, zero custo, zero latência de API externa, suficiente para bases de até ~10k entradas. Embeddings vetoriais estão no roadmap para escala maior.

**Por que um provider plugável?**
O sistema não depende de nenhum LLM específico. Trocar de Gemini para B3GPT é só mudar 3 linhas no `.env` e reiniciar.
