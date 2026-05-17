"""
orchestrator.py
Central pipeline coordinator.

Flow:
  Input
    → Normalizer (with KB context)
    → [Parallel: Ambiguity + Risk + Rules + Gap + Coverage]
    → Knowledge Aggregator (institutional memory)
    → Synthesis (fresh findings + historical context)
    → Response

This is the ONLY place that knows about pipeline order and timing.
Engines know nothing about each other.
"""

import asyncio
import time
import uuid
from typing import Optional

from models.schemas import (
    AnalysisRequest, AnalysisResponse, EngineStatus, EngineTimings
)
from providers.factory import get_provider
from utils.config      import settings
from engines import normalizer, ambiguity, risk, rules, gap, coverage, synthesis
import engines.knowledge_aggregator as knowledge_aggregator_mod
import engines.traceability as traceability_mod
import engines.requirements_inference as inference_mod
from repositories.analysis import AnalysisRepository
from repositories.project  import ProjectRepository

analysis_repo = AnalysisRepository()
project_repo  = ProjectRepository()


async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """
    Run the full hybrid pipeline for a single requirement.
    Returns a complete AnalysisResponse regardless of partial failures.
    """
    request_id = str(uuid.uuid4())
    provider   = get_provider()
    timings    = EngineTimings()
    pipeline_start = time.perf_counter()

    # Language instruction injected into every engine prompt
    lang = settings.ENGINE_LANGUAGE.lower()
    lang_instruction = f"\n\nIMPORTANT: Return ALL text fields (title, description, suggestion, summary, verdict, etc.) in {lang}. Only keep JSON keys in English."

    response = AnalysisResponse(
        request_id=request_id,
        project_id=request.project_id,
        status=EngineStatus.RUNNING,
    )

    # ── Stage 1: Normalize (with Knowledge Layer context) ────────────────────
    t0 = time.perf_counter()
    try:
        # Fetch relevant corporate knowledge before normalizing
        from utils.knowledge_context import build_context
        knowledge_ctx = build_context(
            requirement=request.requirement,
            project_id=request.project_id,
        )

        normalized = await normalizer.run(
            requirement=request.requirement + lang_instruction,
            context=request.context or "",
            provider=provider,
            max_tokens=settings.ENGINE_MAX_TOKENS,
            knowledge_context=knowledge_ctx,
        )
        response.normalized = normalized
    except Exception as e:
        response.status = EngineStatus.ERROR
        response.error  = f"Normalizer failed: {e}"
        return response
    timings.normalizer = round(time.perf_counter() - t0, 2)

    # ── Stage 2: Parallel engines ────────────────────────────────────────────
    # Inject language instruction into normalized intent so all engines receive it
    normalized.intent = normalized.intent + lang_instruction

    sem = asyncio.Semaphore(settings.ENGINE_CONCURRENCY)

    async def run_engine(engine_fn, engine_name: str):
        async with sem:
            t = time.perf_counter()
            try:
                result = await asyncio.wait_for(
                    engine_fn(normalized, provider, settings.ENGINE_MAX_TOKENS),
                    timeout=settings.ENGINE_TIMEOUT,
                )
                return engine_name, result, round(time.perf_counter() - t, 2), None
            except asyncio.TimeoutError:
                return engine_name, None, round(time.perf_counter() - t, 2), "timeout"
            except Exception as e:
                return engine_name, None, round(time.perf_counter() - t, 2), str(e)

    # Determine which engines to run
    requested = set(request.engines) if request.engines else None

    async def run_inference(normalized, provider, max_tokens):
        """Wrapper to match engine_map signature."""
        return await inference_mod.run(
            normalized=normalized,
            ambiguity=None, risk=None, rules=None, gap=None,
            provider=provider,
            max_tokens=max_tokens,
            language=settings.ENGINE_LANGUAGE,
        )

    engine_map = {
        "ambiguity": ambiguity.run,
        "risk":      risk.run,
        "rules":     rules.run,
        "gap":       gap.run,
        "coverage":  coverage.run,
        "inference": run_inference,
    }
    engines_to_run = {
        name: fn for name, fn in engine_map.items()
        if requested is None or name in requested
    }

    parallel_results = await asyncio.gather(
        *[run_engine(fn, name) for name, fn in engines_to_run.items()]
    )

    errors = []
    amb_result = risk_result = rules_result = gap_result = cov_result = None

    for engine_name, result, elapsed, error in parallel_results:
        if error:
            errors.append(f"{engine_name}: {error}")
            continue
        if engine_name == "ambiguity":
            response.ambiguity = amb_result = result
            timings.ambiguity  = elapsed
        elif engine_name == "risk":
            response.risk = risk_result = result
            timings.risk  = elapsed
        elif engine_name == "rules":
            response.rules = rules_result = result
            timings.rules  = elapsed
        elif engine_name == "gap":
            response.gap = gap_result = result
            timings.gap  = elapsed
        elif engine_name == "coverage":
            response.coverage = cov_result = result
            timings.coverage  = elapsed
        elif engine_name == "inference":
            response.inference = result
            timings.__dict__["inference"] = elapsed

    # ── Stage 2.5: Knowledge Aggregator + Traceability (parallel) ────────────
    # Both run after the 5 engines, before Synthesis.
    ka_result  = None
    tra_result = None

    t0 = time.perf_counter()
    try:
        ka_task  = knowledge_aggregator_mod.run(
            requirement=request.requirement,
            normalized=normalized,
            project_id=request.project_id,
        )
        tra_task = traceability_mod.run(
            normalized=normalized,
            ambiguity=amb_result,
            risk=risk_result,
            rules=rules_result,
            gap=gap_result,
            coverage=cov_result,
            requirement=request.requirement,
            project_id=request.project_id,
        )
        ka_result, tra_result = await asyncio.gather(ka_task, tra_task, return_exceptions=True)

        if isinstance(ka_result, Exception):
            errors.append(f"knowledge_aggregator: {ka_result}")
            ka_result = None
        else:
            response.knowledge = ka_result.to_dict()

        if isinstance(tra_result, Exception):
            errors.append(f"traceability: {tra_result}")
            tra_result = None
        else:
            response.traceability = tra_result

    except Exception as e:
        errors.append(f"stage_2_5: {e}")
    timings.__dict__["knowledge"]     = round(time.perf_counter() - t0, 2)
    timings.__dict__["traceability"]  = timings.__dict__["knowledge"]

    # ── Stage 3: Synthesis ───────────────────────────────────────────────────
    results_available = sum(
        r is not None for r in [amb_result, risk_result, rules_result, gap_result, cov_result]
    )

    if results_available >= 2:
        from models.schemas import (
            AmbiguityResult, RiskResult, RulesResult, GapResult, CoverageResult
        )
        t0 = time.perf_counter()
        try:
            # Build enriched normalized with knowledge context for Synthesis
            synth_normalized = normalized
            if ka_result and ka_result.context_block:
                # Append institutional context to intent so Synthesis receives it
                synth_normalized.intent = (
                    normalized.intent + "\n\n" + ka_result.context_block
                )

            synth = await synthesis.run(
                normalized=synth_normalized,
                ambiguity=amb_result  or AmbiguityResult(score=50, summary="Engine did not run"),
                risk=risk_result      or RiskResult(score=50, summary="Engine did not run", risk_level="medium"),
                rules=rules_result    or RulesResult(score=50, summary="Engine did not run"),
                gap=gap_result        or GapResult(score=50, summary="Engine did not run"),
                coverage=cov_result   or CoverageResult(score=50, summary="Engine did not run"),
                provider=provider,
                max_tokens=settings.ENGINE_MAX_TOKENS,
            )
            response.synthesis = synth
        except Exception as e:
            errors.append(f"synthesis: {e}")
        timings.synthesis = round(time.perf_counter() - t0, 2)

    timings.total = round(time.perf_counter() - pipeline_start, 2)
    response.timings = timings
    response.status  = EngineStatus.ERROR if errors and results_available == 0 else EngineStatus.DONE
    if errors:
        response.error = "; ".join(errors)

    # ── Auto-save to database ─────────────────────────────────────────────────
    try:
        from utils.id_detector import detect_story_id
        from repositories.analysis import AnalysisRepository

        detected_id = detect_story_id(request.requirement)
        _repo = AnalysisRepository()

        _repo.save(
            result=response,
            requirement=request.requirement,
            context=request.context,
            story_id=detected_id,          # None if no ID detected
            project_id=request.project_id,
            provider=provider.provider_name,
            model=provider.model_name,
        )
    except Exception:
        pass

    return response
