"""
engines/artifact_generator.py
Artifact Generation Engine v2 — Context-Driven

Uses REAL data from the full pipeline:
  - SCs and CTs from Traceability v2
  - RNs and CAs from requirement_parser
  - Risks from Risk Engine
  - Gaps from Gap Engine
  - Historical context from Knowledge Layer
  - RFs/RNFs from Inference Engine

Profiles:
  QA    → Gherkin (BDD), Test Cases, Evidence Template
  Dev   → Automation Skeletons, Gap Analysis técnico
  PO    → Critérios de Aceite, Gap Analysis funcional, Business Value
  Audit → Risk Report, RTM exportável
"""

import uuid
from typing import Optional
from models.schemas import (
    NormalizedRequirement, AmbiguityResult, RiskResult, RulesResult,
    GapResult, CoverageResult, TraceabilityResult, SynthesisResult,
    InferenceResult, ArtifactResult, ArtifactItem, EngineStatus,
)
from providers.base import BaseProvider, CompletionRequest


# ── Context builder ───────────────────────────────────────────────────────────

def _build_context(
    normalized:   NormalizedRequirement,
    risk:         Optional[RiskResult],
    gap:          Optional[GapResult],
    rules:        Optional[RulesResult],
    traceability: Optional[TraceabilityResult],
    inference:    Optional[InferenceResult],
    synthesis:    Optional[SynthesisResult],
    knowledge:    Optional[dict],
    story_id:     Optional[str],
) -> dict:
    """Build structured context from all pipeline outputs."""

    # RNs and CAs from parser (exact texts)
    rns = normalized.rns or {}
    cas = normalized.cas or {}

    # Scenarios and test cases from Traceability v2
    scenarios  = getattr(traceability, 'scenarios',  []) if traceability else []
    test_cases = getattr(traceability, 'test_cases', []) if traceability else []
    rtm        = (traceability.coverage_detail or {}).get("_rtm", []) if traceability else []

    # Risk findings
    risks = []
    if risk and risk.findings:
        for f in risk.findings:
            risks.append({
                "id":          f.id,
                "title":       f.title,
                "description": f.description[:200],
                "severity":    f.severity.value,
                "suggestion":  f.suggestion or "",
            })

    # Gap findings
    gaps = []
    if gap:
        for f in gap.findings:
            gaps.append({
                "id":          f.id,
                "title":       f.title,
                "description": f.description[:200],
                "severity":    f.severity.value,
            })
        missing = gap.missing or []
    else:
        missing = []

    # Inferred requirements
    rfs  = [{"id": r.id, "title": r.title, "description": r.description, "priority": r.priority, "origin": r.origin} for r in (inference.rfs  if inference else [])]
    rnfs = [{"id": r.id, "title": r.title, "description": r.description, "priority": r.priority, "category": r.category} for r in (inference.rnfs if inference else [])]

    # Knowledge context
    kb_entries = (knowledge or {}).get("kb_entries", [])
    defects    = (knowledge or {}).get("defects_summary", {})
    has_hist   = (knowledge or {}).get("has_history", False)
    version_trend = (knowledge or {}).get("version_trend", "first")

    return {
        "story_id":      story_id or "",
        "intent":        normalized.intent,
        "actors":        normalized.actors or [],
        "rns":           rns,
        "cas":           cas,
        "scenarios":     scenarios,
        "test_cases":    test_cases,
        "rtm":           rtm,
        "risks":         risks,
        "gaps":          gaps,
        "missing":       missing,
        "rfs":           rfs,
        "rnfs":          rnfs,
        "rules_found":   (rules.rules_found or []) if rules else [],
        "correlations":  [(c.title + ": " + c.description[:100]) for c in (synthesis.correlations or [])] if synthesis else [],
        "kb_entries":    kb_entries[:6],
        "defects":       defects,
        "has_history":   has_hist,
        "version_trend": version_trend,
    }


def _fmt_rns(ctx: dict, limit: int = 10) -> str:
    lines = []
    for rn_id, text in sorted(ctx["rns"].items())[:limit]:
        lines.append(f"  {rn_id}: {text[:200]}")
    return "\n".join(lines) if lines else "  Sem RNs estruturadas."


def _fmt_cas(ctx: dict, limit: int = 10) -> str:
    lines = []
    for ca_id, text in sorted(ctx["cas"].items())[:limit]:
        lines.append(f"  {ca_id}: {text[:200]}")
    return "\n".join(lines) if lines else "  Sem CAs estruturados."


def _fmt_scenarios(ctx: dict) -> str:
    lines = []
    for sc in ctx["scenarios"][:8]:
        rns = ", ".join(sc.get("origin_rn", []))
        cas = ", ".join(sc.get("origin_ca", []))
        tp  = sc.get("type", "positive")
        lines.append(f"  {sc['id']} [{tp}] {sc.get('title','')} → RN:{rns} CA:{cas}")
    return "\n".join(lines) if lines else "  Sem cenários gerados."


def _fmt_test_cases(ctx: dict) -> str:
    lines = []
    for ct in ctx["test_cases"][:10]:
        lines.append(f"  {ct.get('title', ct.get('id',''))}")
    return "\n".join(lines) if lines else "  Sem casos de teste."


def _fmt_risks(ctx: dict) -> str:
    lines = []
    for r in ctx["risks"][:8]:
        lines.append(f"  [{r['severity'].upper()}] {r['id']}: {r['title']}")
    return "\n".join(lines) if lines else "  Sem riscos identificados."


def _fmt_gaps(ctx: dict) -> str:
    lines = []
    for g in ctx["gaps"][:6]:
        lines.append(f"  [{g['severity'].upper()}] {g['id']}: {g['title']}")
    for m in ctx["missing"][:4]:
        lines.append(f"  [GAP] {m}")
    return "\n".join(lines) if lines else "  Sem gaps identificados."


def _fmt_kb(ctx: dict) -> str:
    lines = []
    if ctx["has_history"]:
        lines.append(f"  Tendência: {ctx['version_trend']}")
    defects = ctx["defects"]
    if defects and defects.get("total", 0) > 0:
        lines.append(f"  Defeitos históricos: {defects['total']} total, {defects.get('open',0)} abertos")
    for e in ctx["kb_entries"]:
        tags = e.get("tags", [])
        conf = next((t for t in tags if t.startswith("confidence:")), None)
        conf_v = f" (conf: {conf.split(':')[1]})" if conf else ""
        lines.append(f"  [{e.get('category','')}] {e.get('title','')}{conf_v}")
    return "\n".join(lines) if lines else "  Sem histórico corporativo."


# ── QA: Gherkin ──────────────────────────────────────────────────────────────

async def _gen_gherkin(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    sc_block = _fmt_scenarios(ctx)
    ct_block = _fmt_test_cases(ctx)
    risk_block = _fmt_risks(ctx)

    prompt = f"""Você é um especialista em BDD e Quality Engineering.
Gere um arquivo .feature Gherkin completo em {lang} usando os dados REAIS do pipeline.

HISTÓRIA: {ctx['story_id']}
INTENT: {ctx['intent']}
ATORES: {', '.join(ctx['actors'])}

CENÁRIOS GERADOS PELO TRACEABILITY ENGINE:
{sc_block}

CASOS DE TESTE (use como base para os Scenarios):
{ct_block}

RISCOS IDENTIFICADOS (gere Scenarios negativos para cada um):
{risk_block}

REGRAS DE NEGÓCIO:
{_fmt_rns(ctx, 8)}

CRITÉRIOS DE ACEITE:
{_fmt_cas(ctx, 8)}

INSTRUÇÕES:
- Feature tag e descrição com o valor de negócio real
- Background com pré-condições comuns dos cenários
- Para cada SC positivo: um Scenario com steps reais
- Para cada risco crítico/high: um Scenario negativo
- Tags obrigatórias: @smoke @regression @critical conforme severidade
- Tags de rastreabilidade: @RN-XX @CA-XX @RSK-XXX por cenário
- Scenario Outline com Examples para boundary values quando aplicável
- Steps específicos e acionáveis — não genéricos

Retorne APENAS o conteúdo .feature."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── QA: Test Cases ────────────────────────────────────────────────────────────

async def _gen_test_cases(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    prompt = f"""Você é um QA Engineer especialista em casos de teste detalhados.
Gere casos de teste completos em {lang} baseados nos dados REAIS do pipeline.

HISTÓRIA: {ctx['story_id']}
INTENT: {ctx['intent']}

CASOS DE TESTE DA RTM (expanda cada um):
{_fmt_test_cases(ctx)}

REGRAS DE NEGÓCIO:
{_fmt_rns(ctx, 10)}

CRITÉRIOS DE ACEITE:
{_fmt_cas(ctx, 10)}

RISCOS (gere CTs negativos):
{_fmt_risks(ctx)}

GAPS (documente como CTs missing):
{_fmt_gaps(ctx)}

FORMATO OBRIGATÓRIO para cada caso:
## CT-XXX - RN-XX | CA-XX: Título descritivo
**Tipo:** Funcional | Negativo | Boundary | Segurança | Performance
**Prioridade:** Critical | High | Medium | Low
**Rastreabilidade:** RN-XX → CA-XX → SC-XXX
**Pré-condições:**
- [específicas]
**Massa de teste:**
- [dados concretos, não genéricos]
**Passos:**
1. [passo específico]
**Resultado esperado:** [vinculado ao CA]
**Automatizável:** Sim | Não
**Observações:** [histórico relevante se houver]

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── QA: Evidence Template ─────────────────────────────────────────────────────

async def _gen_evidence(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    ct_ids = [ct.get("id", "") for ct in ctx["test_cases"][:12]]
    ca_ids = list(ctx["cas"].keys())[:10]

    prompt = f"""Você é um QA Engineer especialista em evidências de teste e auditoria.
Gere um template de evidências em {lang} para a história {ctx['story_id']}.

CASOS DE TESTE A EVIDENCIAR:
{chr(10).join('  ' + ct for ct in ct_ids) if ct_ids else '  Sem CTs definidos'}

CRITÉRIOS DE ACEITE A VALIDAR:
{_fmt_cas(ctx, 10)}

RISCOS QUE PRECISAM DE EVIDÊNCIA ESPECÍFICA:
{_fmt_risks(ctx)}

INSTRUÇÕES:
- Cabeçalho: história, versão, data, executor, ambiente, build
- Tabela de execução: CT-ID | Descrição | Status | Evidência | Defeito | Observação
- Para cada CT: placeholder de screenshot específico [SCREENSHOT: o que capturar]
- Checklist de CAs validados com campo de aprovação
- Seção de defeitos encontrados durante execução
- Seção de aprovação com assinatura QA Lead e Dev Lead
- Referências explícitas aos riscos críticos que precisam evidência

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── Dev: Automation Skeletons ─────────────────────────────────────────────────

async def _gen_skeletons(ctx: dict, provider: BaseProvider, max_tokens: int) -> str:
    auto_cts = [ct for ct in ctx["test_cases"] if ct.get("automated", True)][:8]
    ct_block = "\n".join(f"  {ct.get('title', ct.get('id',''))}" for ct in auto_cts)

    prompt = f"""Você é um Dev Engineer especialista em automação de testes.
Gere automation skeletons em Markdown para a história {ctx['story_id']}.

CASOS DE TESTE AUTOMATIZÁVEIS:
{ct_block if ct_block else '  Sem CTs automatizáveis definidos'}

GAPS QUE PRECISAM DE COBERTURA (adicione como TODOs):
{_fmt_gaps(ctx)}

INSTRUÇÕES — Gere skeletons para 3 frameworks:

## Robot Framework (.robot)
- *** Settings ***: imports necessários
- *** Variables ***: sem hardcode, use ${{ENV:VAR}}
- *** Test Cases ***: um test case por CT automatizável
- *** Keywords ***: keywords atômicas reutilizáveis
- Documentação inline referenciando RN e CA de cada test

## Playwright TypeScript (.spec.ts)
- describe() agrupando por funcionalidade
- it() por CT com nome descritivo
- Page Object class stub
- TODO comments para gaps identificados

## Pytest (.py)
- Fixtures para setup/teardown
- @pytest.mark.parametrize para boundary values
- Classes agrupando por funcionalidade
- TODO comments para gaps

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── Dev: Gap Analysis técnico ─────────────────────────────────────────────────

async def _gen_gap_tech(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    prompt = f"""Você é um arquiteto de software especialista em análise de requisitos.
Gere uma análise de gaps técnica em {lang} para a história {ctx['story_id']}.

INTENT: {ctx['intent']}

GAPS IDENTIFICADOS:
{_fmt_gaps(ctx)}

RISCOS TÉCNICOS:
{_fmt_risks(ctx)}

REQUISITOS NÃO-FUNCIONAIS INFERIDOS:
{chr(10).join(f"  {r['id']} [{r['category']}]: {r['title']}" for r in ctx['rnfs'][:8]) if ctx['rnfs'] else '  Sem RNFs inferidos'}

INSTRUÇÕES — Foco técnico:
Estrutura em Markdown:
## Sumário Executivo
## Gaps por Camada (Frontend / Backend / API / Banco / Integração)
## Tabela: Gap | Impacto Técnico | Prioridade | Recomendação
## Dependências Faltantes
## Requisitos Não-Funcionais sem Especificação Técnica
## Recomendações Priorizadas

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── PO: Critérios de Aceite ───────────────────────────────────────────────────

async def _gen_ca(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    prompt = f"""Você é um Product Owner especialista em requisitos.
Gere os Critérios de Aceite completos em {lang} para a história {ctx['story_id']}.

CAs JÁ EXISTENTES (use como base):
{_fmt_cas(ctx, 15)}

GAPS IDENTIFICADOS (gere CAs novos para cada um):
{_fmt_gaps(ctx)}

RISCOS CRÍTICOS (gere CAs de segurança):
{_fmt_risks(ctx)}

REQUISITOS FUNCIONAIS INFERIDOS (valide se têm CA):
{chr(10).join(f"  {r['id']}: {r['title']} (origem: {r['origin']})" for r in ctx['rfs'][:6]) if ctx['rfs'] else '  Sem RFs inferidos'}

INSTRUÇÕES:
- Formato: "DADO [contexto] QUANDO [ação] ENTÃO [resultado esperado]"
- Inclua os CAs existentes + novos CAs para gaps e riscos
- Marque CAs derivados de gaps: "(NOVO — gap identificado: GAP-XXX)"
- Marque CAs de risco: "(CRÍTICO — RSK-XXX)"
- Inclua CAs não-funcionais (performance, segurança, acessibilidade)

Estrutura em Markdown:
## Critérios de Aceite — {ctx['story_id']}
### Funcionais
### Segurança e Acesso
### Performance e SLA
### Acessibilidade e UX
### Novos (derivados de gaps)

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── PO: Gap Analysis funcional ────────────────────────────────────────────────

async def _gen_gap_func(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    prompt = f"""Você é um Product Owner e especialista em produto.
Gere uma análise de gaps funcional em {lang} para a história {ctx['story_id']}.

INTENT: {ctx['intent']}
ATORES: {', '.join(ctx['actors'])}

GAPS IDENTIFICADOS:
{_fmt_gaps(ctx)}

RISCOS AO USUÁRIO:
{_fmt_risks(ctx)}

INSTRUÇÕES — Linguagem de NEGÓCIO, sem jargão técnico:
Estrutura em Markdown:
## O que o usuário NÃO conseguirá fazer
## Fluxos de Negócio Incompletos
## Tabela: Gap | Impacto no Usuário | Prioridade | Recomendação ao PO
## Dependências Funcionais Faltantes
## Recomendações antes do Go-Live

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── PO: Business Value ────────────────────────────────────────────────────────

async def _gen_business_value(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    kb_block = _fmt_kb(ctx)
    prompt = f"""Você é um especialista em produto e valor de negócio.
Gere um relatório de Business Value em {lang} para a história {ctx['story_id']}.

INTENT: {ctx['intent']}
ATORES: {', '.join(ctx['actors'])}

RISCOS AO NEGÓCIO (traduza em linguagem de negócio):
{_fmt_risks(ctx)}

O QUE AINDA FALTA (gaps traduzidos para UX):
{_fmt_gaps(ctx)}

HISTÓRICO CORPORATIVO:
{kb_block}

INSTRUÇÕES — Linguagem de NEGÓCIO, sem jargão técnico:
Estrutura em Markdown:
## Valor entregue ao usuário
## O que muda na operação
## Riscos ao negócio (traduzidos de riscos técnicos)
## O que ainda não será possível fazer
## Priorização recomendada (valor vs esforço vs risco)
## Lições do histórico corporativo
## Como medir o sucesso (KPIs sugeridos)

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── Audit: Risk Report ────────────────────────────────────────────────────────

async def _gen_risk_report(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    kb_block = _fmt_kb(ctx)
    prompt = f"""Você é um especialista em gestão de riscos e auditoria de sistemas.
Gere um Risk Report completo em {lang} para a história {ctx['story_id']}.

RISCOS IDENTIFICADOS PELO PIPELINE:
{_fmt_risks(ctx)}

CONTEXTO HISTÓRICO CORPORATIVO:
{kb_block}

CORRELAÇÕES DO SYNTHESIS ENGINE:
{chr(10).join('  ' + c for c in ctx['correlations'][:5]) if ctx['correlations'] else '  Sem correlações identificadas'}

INSTRUÇÕES:
Estrutura em Markdown:
## Risk Report — {ctx['story_id']}
## Sumário Executivo
## Matriz de Riscos (tabela: ID | Descrição | Categoria | Severidade | Probabilidade | Impacto | Mitigação)
## Riscos Detalhados (um por finding real do Risk Engine)
## Correlação Histórica (com % confiança do Knowledge Layer)
## Compliance e Regulatório (LGPD, ISO, regulatórios do domínio)
## Plano de Mitigação Priorizado
## Aprovações Requeridas antes do Go-Live

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── Audit: RTM exportável ─────────────────────────────────────────────────────

async def _gen_rtm_export(ctx: dict, provider: BaseProvider, max_tokens: int, lang: str) -> str:
    # Build RTM table from real data
    rtm_rows = ctx.get("rtm", [])
    if not rtm_rows and ctx.get("test_cases"):
        rtm_rows = [
            {
                "test_id":   ct.get("id", ""),
                "rn":        (ct.get("rns") or ["—"])[0],
                "ca":        (ct.get("cas") or ["—"])[0],
                "title":     ct.get("title", ""),
                "risk":      (ct.get("risks") or [""])[0],
                "gap":       (ct.get("gaps")  or [""])[0],
                "priority":  ct.get("priority", "medium"),
                "automated": "Sim" if ct.get("automated", True) else "Não",
            }
            for ct in ctx["test_cases"][:20]
        ]

    rtm_md = "| ID do Teste | RN | CA | Título do Caso de Teste | Risco | Gap | Prioridade | Automatizável |\n"
    rtm_md += "|-------------|----|----|------------------------|-------|-----|------------|---------------|\n"
    for row in rtm_rows:
        rtm_md += (
            f"| {row.get('test_id','')} | {row.get('rn','—')} | {row.get('ca','—')} | "
            f"{row.get('title','')[:50]} | {row.get('risk','—') or '—'} | "
            f"{row.get('gap','—') or '—'} | {row.get('priority','medium')} | "
            f"{'Sim' if row.get('automated') else 'Não'} |\n"
        )

    cov = ctx.get("coverage_detail", {})
    overall = (cov.get("overall_pct") or
               getattr(ctx.get("traceability"), "overall_coverage", 0) or 0)

    prompt = f"""Você é um especialista em rastreabilidade e auditoria de requisitos.
Gere uma RTM exportável completa em {lang} para a história {ctx['story_id']}.

RTM GERADA PELO TRACEABILITY ENGINE:
{rtm_md}

COBERTURA GERAL: {overall}%

REQUISITOS SEM COBERTURA:
{chr(10).join('  ' + u for u in (cov.get('uncovered_rns', []) + cov.get('uncovered_cas', []))) or '  Todos cobertos'}

CENÁRIOS FALTANDO:
{chr(10).join('  ' + m for m in cov.get('missing_scenarios', [])) or '  Nenhum'}

INSTRUÇÕES:
- Reproduza a RTM acima com formatação limpa
- Adicione coluna de Status (Pendente | Em execução | Executado | Bloqueado)
- Adicione cobertura por categoria funcional/segurança/performance/compliance/usabilidade
- Inclua legenda e instruções de uso para auditoria
- Adicione seção de gaps críticos que precisam de atenção antes do go-live
- Formate para exportação — tabelas bem estruturadas

Retorne APENAS o Markdown."""

    r = await provider.complete(CompletionRequest(prompt=prompt, max_tokens=max_tokens))
    return r.content


# ── Main engine ───────────────────────────────────────────────────────────────

async def run(
    normalized:   NormalizedRequirement,
    ambiguity:    Optional[AmbiguityResult]     = None,
    risk:         Optional[RiskResult]          = None,
    rules:        Optional[RulesResult]         = None,
    gap:          Optional[GapResult]           = None,
    coverage:     Optional[CoverageResult]      = None,
    traceability: Optional[TraceabilityResult]  = None,
    inference:    Optional[InferenceResult]     = None,
    synthesis:    Optional[SynthesisResult]     = None,
    knowledge:    Optional[dict]                = None,
    provider:     BaseProvider                  = None,
    max_tokens:   int                           = 2000,
    language:     str                           = "portuguese",
    story_id:     Optional[str]                 = None,
    profiles:     Optional[list[str]]           = None,
) -> ArtifactResult:

    result = ArtifactResult(story_id=story_id)
    lang   = "português" if "port" in language.lower() else "english"

    # Build rich context from pipeline
    ctx = _build_context(
        normalized, risk, gap, rules,
        traceability, inference, synthesis,
        knowledge, story_id,
    )
    ctx["traceability"]     = traceability
    ctx["coverage_detail"]  = getattr(traceability, "coverage_detail", {}) or {}

    active = set(profiles or ["qa", "dev", "po", "audit"])
    artifacts = []

    async def add(profile, art_type, title, coro, fmt):
        try:
            content = await coro
            artifacts.append(ArtifactItem(
                id=f"ART-{uuid.uuid4().hex[:6].upper()}",
                profile=profile,
                type=art_type,
                title=title,
                content=content,
                format=fmt,
                story_id=story_id,
            ))
        except Exception as e:
            artifacts.append(ArtifactItem(
                id=f"ART-ERR",
                profile=profile,
                type=art_type,
                title=f"{title} (erro)",
                content=f"Erro ao gerar: {e}",
                format=fmt,
                story_id=story_id,
            ))

    if "qa" in active:
        await add("qa", "gherkin",    "Cenários BDD / Gherkin",
                  _gen_gherkin(ctx, provider, max_tokens, lang),    "gherkin")
        await add("qa", "test_cases", "Casos de Teste Detalhados",
                  _gen_test_cases(ctx, provider, max_tokens, lang), "markdown")
        await add("qa", "evidence",   "Template de Evidências",
                  _gen_evidence(ctx, provider, max_tokens, lang),   "markdown")

    if "dev" in active:
        await add("dev", "skeleton",     "Automation Skeletons (RF + Playwright + pytest)",
                  _gen_skeletons(ctx, provider, max_tokens),            "markdown")
        await add("dev", "gap_analysis", "Gap Analysis Técnico",
                  _gen_gap_tech(ctx, provider, max_tokens, lang),       "markdown")

    if "po" in active:
        await add("po", "ca",             "Critérios de Aceite",
                  _gen_ca(ctx, provider, max_tokens, lang),             "markdown")
        await add("po", "gap_analysis",   "Gap Analysis Funcional",
                  _gen_gap_func(ctx, provider, max_tokens, lang),       "markdown")
        await add("po", "business_value", "Business Value / Valor do Negócio",
                  _gen_business_value(ctx, provider, max_tokens, lang), "markdown")

    if "audit" in active:
        await add("audit", "risk_report", "Risk Report",
                  _gen_risk_report(ctx, provider, max_tokens, lang),    "markdown")
        await add("audit", "rtm",         "RTM Exportável",
                  _gen_rtm_export(ctx, provider, max_tokens, lang),     "markdown")

    result.artifacts = artifacts
    result.status    = EngineStatus.DONE
    result.summary   = (
        f"{len(artifacts)} artefato(s) gerado(s) com contexto real do pipeline "
        f"({len(ctx['rns'])} RNs, {len(ctx['cas'])} CAs, "
        f"{len(ctx['scenarios'])} cenários, {len(ctx['test_cases'])} CTs)."
    )
    return result
