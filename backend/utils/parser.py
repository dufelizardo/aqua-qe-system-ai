"""
utils/parser.py
Safe JSON extraction from LLM responses.
All engines use this — never parse raw LLM output directly.
"""

import json
import re


def extract_json(text: str) -> dict | list:
    """
    Robustly extract JSON from LLM output.
    Handles: raw JSON, ```json fences, JSON inside prose, truncated responses.
    """
    # 1. Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    text = text.strip()

    # 2. Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Find first { or [ and try from there
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        end   = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                continue

    # 4. Truncated JSON recovery — try to close open structure
    start = text.find('{')
    if start != -1:
        fragment = text[start:]
        # Count open braces to detect truncation
        depth = 0
        for ch in fragment:
            if ch == '{': depth += 1
            elif ch == '}': depth -= 1
        if depth > 0:
            # Close any open string first
            if fragment.count('"') % 2 != 0:
                fragment += '"'
            # Close any open arrays/objects
            fragment += ']' * fragment.count('[')
            fragment += '}' * depth
            try:
                return json.loads(fragment)
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON found in LLM response. Preview: {text[:200]}")


def safe_int(val, default: int = 50) -> int:
    """Safely coerce a value to int, clamped 0-100."""
    try:
        return max(0, min(100, int(val)))
    except (TypeError, ValueError):
        return default
