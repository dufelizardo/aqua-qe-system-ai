"""
utils/semantic_search.py
Knowledge Layer 3c — Semantic Search (TF-IDF based)

Finds similar KB entries by meaning, not just exact keywords.
No embeddings needed — works offline, zero cost.

Examples:
  "timeout de pagamento" finds "falha de gateway"
  "bloqueio de conta" finds "tentativas inválidas"
  "auditoria ISIN" finds "compliance regulatório"

Uses TF-IDF weighting so rare domain terms matter more than common words.
"""

import re
import math
from typing import Optional
from repositories.knowledge import KnowledgeRepository


# ── Tokenizer ─────────────────────────────────────────────────────────────────

STOPWORDS = {
    # Portuguese
    'de','da','do','das','dos','em','no','na','nos','nas','um','uma',
    'o','a','os','as','e','ou','que','se','para','com','por','ao','à',
    'deve','deverá','sendo','como','quando','onde','qual','este','esta',
    'não','sem','após','antes','durante','sobre','cada','todo','toda',
    'ser','ter','fazer','sistema','usuário','usuário','aplicação',
    # English
    'the','an','and','or','to','of','in','on','at','for','with',
    'is','are','be','should','must','shall','will','may','can',
    'system','user','application','service',
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r'\b[A-Za-zÀ-ÿ]{3,}\b', text.lower())
    return [w for w in words if w not in STOPWORDS]


def compute_tf(tokens: list[str]) -> dict[str, float]:
    tf = {}
    total = len(tokens) or 1
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    return {t: count / total for t, count in tf.items()}


def compute_idf(corpus: list[list[str]]) -> dict[str, float]:
    N = len(corpus) or 1
    df = {}
    for doc in corpus:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    return {term: math.log(N / (1 + count)) for term, count in df.items()}


def tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = compute_tf(tokens)
    return {t: tf[t] * idf.get(t, 0) for t in tf}


def cosine_similarity(v1: dict, v2: dict) -> float:
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    dot    = sum(v1[t] * v2[t] for t in common)
    norm1  = math.sqrt(sum(v ** 2 for v in v1.values()))
    norm2  = math.sqrt(sum(v ** 2 for v in v2.values()))
    return dot / (norm1 * norm2) if norm1 and norm2 else 0.0


# ── Semantic Search ───────────────────────────────────────────────────────────

class SemanticSearch:
    """
    TF-IDF based semantic search over the Knowledge Base.
    Build once, query many times.
    """

    def __init__(self):
        self._entries = []
        self._vectors = []
        self._idf     = {}
        self._built   = False

    def build(self, entries: list[dict]):
        """Build TF-IDF index from KB entries."""
        self._entries = entries
        corpus = []
        for e in entries:
            text   = f"{e.get('title','')} {e.get('description','')} {' '.join(e.get('tags',[]))}"
            tokens = tokenize(text)
            corpus.append(tokens)

        self._idf = compute_idf(corpus)
        self._vectors = [tfidf_vector(doc, self._idf) for doc in corpus]
        self._built = True

    def search(self, query: str, top_k: int = 8, threshold: float = 0.1) -> list[dict]:
        """
        Find KB entries semantically similar to the query.
        Returns entries sorted by relevance with confidence score.
        """
        if not self._built or not self._entries:
            return []

        q_tokens = tokenize(query)
        q_vector = tfidf_vector(q_tokens, self._idf)

        scored = []
        for i, vec in enumerate(self._vectors):
            score = cosine_similarity(q_vector, vec)
            if score >= threshold:
                entry = dict(self._entries[i])
                # Extract occurrence-based confidence from tags
                tags = entry.get("tags", [])
                occ_tag = next((t for t in tags if t.startswith("occurrences:")), None)
                occurrences = int(occ_tag.split(":")[1]) if occ_tag else 1
                conf_tag = next((t for t in tags if t.startswith("confidence:")), None)
                confidence = float(conf_tag.split(":")[1]) if conf_tag else 0.3

                entry["_similarity"]  = round(score, 3)
                entry["_occurrences"] = occurrences
                entry["_confidence"]  = confidence
                entry["_final_score"] = round(score * confidence, 3)
                scored.append(entry)

        # Sort by combined score (similarity × confidence)
        scored.sort(key=lambda x: x["_final_score"], reverse=True)
        return scored[:top_k]

    def search_for_engine(self, query: str, engine: str,
                          project_id: Optional[str] = None) -> list[dict]:
        """
        Engine-specific search — filters by relevant categories.

        Risk Engine    → riscos históricos
        Gap Engine     → gaps recorrentes
        Synthesis      → correlações organizacionais
        Normalizer     → todos (contexto amplo)
        """
        engine_categories = {
            "risk":      ["risco", "comp"],
            "gap":       ["padrao", "heur"],
            "synthesis": ["heur", "risco", "comp"],
            "normalizer":["padrao", "bug", "integ", "gloss", "comp", "risco", "heur"],
        }

        results = self.search(query, top_k=12, threshold=0.08)

        # Filter by engine-relevant categories
        cats = engine_categories.get(engine, [])
        if cats:
            filtered = [r for r in results if r.get("category") in cats]
            # If filtered too strict, relax to top results
            if len(filtered) < 3:
                filtered = results

            # Also apply project filter if provided
            if project_id:
                filtered = [
                    r for r in filtered
                    if r.get("project_id") is None or r.get("project_id") == project_id
                ]

            return filtered[:6]

        return results[:6]


# ── Global instance ───────────────────────────────────────────────────────────
# Built lazily and rebuilt when KB changes

_instance: Optional[SemanticSearch] = None
_last_build_count: int = 0


def get_searcher(project_id: Optional[str] = None, force_rebuild: bool = False) -> SemanticSearch:
    """
    Get or build the global semantic search instance.
    Rebuilds automatically when KB size changes.
    """
    global _instance, _last_build_count

    kb = KnowledgeRepository()
    entries = kb.list(project_id=project_id)

    if _instance is None or force_rebuild or len(entries) != _last_build_count:
        _instance = SemanticSearch()
        _instance.build(entries)
        _last_build_count = len(entries)

    return _instance


def search_kb(query: str, engine: str = "normalizer",
              project_id: Optional[str] = None,
              top_k: int = 6) -> list[dict]:
    """
    Convenience function — search KB semantically for a given engine context.
    """
    searcher = get_searcher(project_id=project_id)
    return searcher.search_for_engine(query, engine, project_id=project_id)


def format_for_prompt(entries: list[dict], engine: str = "normalizer") -> str:
    """
    Format search results as a context block for LLM prompts.
    Includes confidence scores so the LLM can weight the context.
    """
    if not entries:
        return ""

    cat_label = {
        "padrao":"Padrão","bug":"Bug Histórico","integ":"Integração",
        "gloss":"Glossário","comp":"Compliance","risco":"Risco","heur":"Heurística"
    }

    lines = [f"CONTEXTO SEMÂNTICO DA BASE CORPORATIVA (relevante para {engine}):"]
    for e in entries:
        cat   = cat_label.get(e.get("category",""), e.get("category",""))
        sev   = f" [{e.get('severity','')}]" if e.get("severity") else ""
        conf  = e.get("_confidence", 0.3)
        occ   = e.get("_occurrences", 1)
        sim   = e.get("_similarity", 0)

        lines.append(
            f"\n[{cat}{sev}] {e.get('title','')} "
            f"(confiança: {conf:.0%} · visto {occ}x · similaridade: {sim:.0%})"
        )
        lines.append(f"  → {e.get('description','')[:250]}")
        if e.get("mitigation"):
            lines.append(f"  → Mitigação: {e['mitigation'][:150]}")

    lines.append(
        "\nPriorize contexto com maior confiança. "
        "Use como referência histórica, não como verdade absoluta."
    )
    return "\n".join(lines)
