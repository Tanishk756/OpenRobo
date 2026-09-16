import re
from typing import List, Optional, Tuple

from apps.api.models.resource import ResourceModel


def get_trigrams(text: str) -> set[str]:
    clean = f"  {text.lower().strip()} "
    return {clean[i : i + 3] for i in range(len(clean) - 2)}


def compute_trigram_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    s1_clean = s1.lower().strip()
    s2_clean = s2.lower().strip()
    if s1_clean == s2_clean:
        return 1.0
    if len(s1_clean) < 3 or len(s2_clean) < 3:
        return 1.0 if (s1_clean in s2_clean or s2_clean in s1_clean) else 0.0

    tg1 = get_trigrams(s1_clean)
    tg2 = get_trigrams(s2_clean)
    if not tg1 or not tg2:
        return 0.0
    intersection = tg1.intersection(tg2)
    return 2.0 * len(intersection) / (len(tg1) + len(tg2))


def generate_highlight(text: Optional[str], query_tokens: List[str], max_len: int = 140) -> Optional[str]:
    if not text or not query_tokens:
        return None

    # Find first occurrence of any query token
    lower_text = text.lower()
    first_idx = -1
    for token in query_tokens:
        idx = lower_text.find(token.lower())
        if idx != -1:
            if first_idx == -1 or idx < first_idx:
                first_idx = idx

    if first_idx == -1:
        snippet = text[:max_len]
    else:
        start = max(0, first_idx - 30)
        end = min(len(text), start + max_len)
        snippet = ("..." if start > 0 else "") + text[start:end] + ("..." if end < len(text) else "")

    # Bold matching tokens
    highlighted = snippet
    for token in set(query_tokens):
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        highlighted = pattern.sub(lambda m: f"<b>{m.group(0)}</b>", highlighted)

    return highlighted


def calculate_relevance_score(
    res: ResourceModel, query_tokens: List[str], raw_query: str, enable_fuzzy: bool = True
) -> Tuple[float, Optional[str]]:
    """
    Computes a deterministic weighted relevance score for a resource against a query.
    Weights:
      - Weight A: Name / ID match (1.0)
      - Weight B: Domains / Capabilities / Summary match (0.5)
      - Weight C: Description match (0.2)
      - Fuzzy Trigram: Typo tolerance (0.3 - 0.7)
    """
    if not raw_query or not query_tokens:
        return 1.0, None

    q_lower = raw_query.lower().strip()
    name_lower = res.name.lower().strip()
    id_lower = res.id.lower().strip()
    summary_lower = (res.summary or "").lower()
    desc_lower = (res.description or "").lower()
    domains = [d.lower() for d in (res.robotics_domains or [])]
    caps = [c.lower() for c in (res.capabilities or [])]

    score = 0.0
    match_found = False

    # 1. Exact or prefix match on Name / ID (Weight A)
    if q_lower == name_lower or q_lower == id_lower.split("/")[-1]:
        score += 2.0
        match_found = True
    elif name_lower.startswith(q_lower) or any(tok in name_lower for tok in query_tokens):
        score += 1.2
        match_found = True
    elif q_lower in id_lower:
        score += 1.0
        match_found = True

    # 2. Domains and Capabilities match (Weight B)
    domain_matches = sum(1 for tok in query_tokens if any(tok in d for d in domains))
    cap_matches = sum(1 for tok in query_tokens if any(tok in c for c in caps))
    if domain_matches > 0 or cap_matches > 0:
        score += 0.5 * (domain_matches + cap_matches)
        match_found = True

    # 3. Summary match (Weight B)
    if any(tok in summary_lower for tok in query_tokens):
        score += 0.4
        match_found = True

    # 4. Description match (Weight C)
    if any(tok in desc_lower for tok in query_tokens):
        score += 0.2
        match_found = True

    # 5. Fuzzy Trigram similarity (Typo tolerance)
    if enable_fuzzy and len(q_lower) >= 3:
        sim_name = compute_trigram_similarity(q_lower, name_lower)
        short_id = id_lower.split("/")[-1]
        sim_id = compute_trigram_similarity(q_lower, short_id)
        max_sim = max(sim_name, sim_id)
        if max_sim >= 0.35:
            score += max_sim * 0.8
            match_found = True

    if not match_found:
        return 0.0, None

    highlight = generate_highlight(res.description or res.summary or res.name, query_tokens)
    return round(score, 3), highlight
