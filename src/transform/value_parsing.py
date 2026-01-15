from __future__ import annotations

import re
from typing import List, Optional, Tuple

WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")

def strip_markup(text: str) -> str:
    t = text.strip()

    # remove ref tags
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.IGNORECASE | re.DOTALL)
    t = re.sub(r"<ref[^/]*/\s*>", "", t, flags=re.IGNORECASE)

    # remove HTML tags but keep content
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"</?[^>]+>", "", t)

    # collapse whitespace
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return t

def split_listish(text: str) -> List[str]:
    """
    Split typical infobox list values.
    """
    t = strip_markup(text)
    # split on newlines, bullets, semicolons
    parts = re.split(r"[\n;]+|(?:\s*,\s*)", t)
    parts = [p.strip() for p in parts if p.strip()]
    return parts

def extract_wikilinks(text: str) -> List[str]:
    """
    Returns titles from [[Title|label]].
    """
    return [m.group(1).strip() for m in WIKI_LINK_RE.finditer(text)]

def parse_value(text: str) -> Tuple[List[str], List[str]]:
    """
    Returns (linked_titles, literal_parts)
    - linked_titles: list of wiki page titles referenced by [[...]]
    - literal_parts: cleaned string parts with links removed
    """
    linked = extract_wikilinks(text)
    cleaned = strip_markup(text)

    # remove link markup content entirely from cleaned text
    cleaned = WIKI_LINK_RE.sub("", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned).strip()
    # now split remaining literals
    literal_parts = split_listish(cleaned) if cleaned else []
    return linked, literal_parts
