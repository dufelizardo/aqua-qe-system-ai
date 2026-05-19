"""
utils/requirement_parser.py
Structured RN/CA Parser

Extracts every RN and CA from a requirement text with full description.
Runs during normalization — before any engine.

Output example:
  {
    "RN-01": "A funcionalidade deve estar disponível por meio de um card na Home",
    "RN-02": "O card deve ser exibido em ordem alfabética ascendente",
    "CA-01": "Deve existir um card com o título Consulta de ISIN",
    "CA-06": "Usuários sem permissão não devem acessar a funcionalidade por URL direta",
  }

Handles:
  - RN-01, RN-01.1, RN-02.1.a (sub-rules included under parent)
  - CA-01, CA-01.1
  - Numbered lists under each RN/CA
  - Multi-line descriptions
  - Em-dash separators (— )
  - Mixed Portuguese/English
"""

import re
from typing import Optional


# ── ID patterns ───────────────────────────────────────────────────────────────

RN_PATTERN = re.compile(
    r'\b(RN-\d+(?:\.\d+)*)\b',
    re.IGNORECASE
)

CA_PATTERN = re.compile(
    r'\b(CA-\d+(?:\.\d+)*)\b',
    re.IGNORECASE
)

ITEM_HEADER = re.compile(
    r'^\s*((?:RN|CA)-\d+(?:\.\d+)*)\s*[\u2013\u2014\-\.\:]*\s*(.{0,200})',
    re.IGNORECASE
)


def parse_requirements(text: str) -> dict:
    """
    Extract all RN and CA items from requirement text.
    Returns dict: { "RN-01": "full description", "CA-01": "full description" }
    """
    items = {}

    # Split into lines for processing
    lines = text.split('\n')

    current_id   = None
    current_text = []
    in_sublist   = False

    def flush():
        nonlocal current_id, current_text
        if current_id and current_text:
            desc = ' '.join(current_text).strip()
            desc = re.sub(r'\s+', ' ', desc)
            # Clean up list markers
            desc = re.sub(r'^\s*[\-\*\•]\s*', '', desc)
            if desc:
                items[current_id.upper()] = desc[:600]
        current_id   = None
        current_text = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this line starts a new RN/CA
        m = ITEM_HEADER.match(stripped)
        if m:
            flush()
            current_id = m.group(1).upper()
            tail = m.group(2).strip()
            # Remove leading punctuation
            tail = re.sub(r'^[\u2013\u2014\-\.\:]\s*', '', tail).strip()
            if tail:
                current_text = [tail]
            else:
                current_text = []
            in_sublist = False
            continue

        # If we're inside an item, collect continuation lines
        if current_id:
            # Skip section headers that signal a new block
            if re.match(r'^(Regras de Neg|Crit[eé]rios de Aceite|Performance|Seguran|Integra|Cache|Acessib|Logs)', stripped, re.IGNORECASE):
                flush()
                continue

            # Collect bullet/numbered list items as part of description
            if re.match(r'^[\-\*\•\d]+[\.\)]\s', stripped):
                item_text = re.sub(r'^[\-\*\•\d]+[\.\)]\s*', '', stripped)
                current_text.append(item_text)
            else:
                current_text.append(stripped)

    flush()  # Don't forget last item

    # Post-process: merge sub-items into parent if parent text is short
    result = {}
    parents = {}

    for key, val in items.items():
        base = re.match(r'((?:RN|CA)-\d+)(?:\.\d+)*', key)
        if base:
            parent_key = base.group(1)
            if parent_key == key:
                parents[key] = val
            else:
                # Sub-item: append to parent
                if parent_key in parents:
                    parents[parent_key] += f" {val}"
                else:
                    parents[parent_key] = val

    # Also keep sub-items separately for granular reference
    result.update(parents)
    for key, val in items.items():
        if key not in result:
            result[key] = val

    return result


def get_rns(parsed: dict) -> dict:
    """Filter only RN items."""
    return {k: v for k, v in parsed.items() if k.startswith('RN')}


def get_cas(parsed: dict) -> dict:
    """Filter only CA items."""
    return {k: v for k, v in parsed.items() if k.startswith('CA')}


def format_for_prompt(parsed: dict, max_items: int = 30) -> str:
    """
    Format parsed RNs and CAs as a structured block for LLM prompts.
    """
    if not parsed:
        return ""

    rns = {k: v for k, v in parsed.items() if k.startswith('RN')}
    cas = {k: v for k, v in parsed.items() if k.startswith('CA')}

    lines = []

    if rns:
        lines.append("REGRAS DE NEGÓCIO (RN):")
        for k, v in sorted(rns.items())[:max_items]:
            lines.append(f"  {k}: {v[:300]}")

    if cas:
        lines.append("\nCRITÉRIOS DE ACEITE (CA):")
        for k, v in sorted(cas.items())[:max_items]:
            lines.append(f"  {k}: {v[:300]}")

    return "\n".join(lines)


def summary(parsed: dict) -> str:
    """Short summary for logging."""
    rns = sum(1 for k in parsed if k.startswith('RN'))
    cas = sum(1 for k in parsed if k.startswith('CA'))
    return f"{rns} RN(s), {cas} CA(s) extraídos"
