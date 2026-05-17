"""
utils/id_detector.py
Detects story IDs from requirement text.
Patterns: BSAG-1724, US-001, PROJ-123, STORY-42, etc.
"""

import re
from typing import Optional

# Common patterns used in agile teams
ID_PATTERNS = [
    r'\b([A-Z]{2,10}-\d{1,6})\b',        # BSAG-1724, US-001, PROJ-123
    r'\b(US-\d{1,6})\b',                   # US-001
    r'\b(HU-\d{1,6})\b',                   # HU-001 (Historia de Usuario)
    r'\b(STORY-\d{1,6})\b',               # STORY-42
    r'\b(REQ-\d{1,6})\b',                 # REQ-001
    r'\b(TASK-\d{1,6})\b',               # TASK-123
]

COMBINED = re.compile('|'.join(ID_PATTERNS), re.IGNORECASE)


def detect_story_id(text: str) -> Optional[str]:
    """
    Extract the first story ID found in the requirement text.
    Returns uppercase ID or None.
    
    Examples:
        "BSAG-1724 [Consulta de ISIN]..." -> "BSAG-1724"
        "US-001: Login do usuário..."      -> "US-001"
        "Sem ID aqui..."                   -> None
    """
    if not text:
        return None
    
    match = COMBINED.search(text)
    if match:
        # Return the first non-None group
        for group in match.groups():
            if group:
                return group.upper()
    return None


def extract_all_ids(text: str) -> list[str]:
    """Extract all story IDs found in text."""
    matches = COMBINED.findall(text)
    ids = []
    for match_groups in matches:
        for group in match_groups:
            if group and group.upper() not in ids:
                ids.append(group.upper())
    return ids
