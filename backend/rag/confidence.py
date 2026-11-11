"""Confidence scoring: how well an answer is backed by the passages it was built from.

Three factors, each 0..1:
  quantity    - how many independent sources actually back the answer's claims
  relevance   - how closely the passages match the question and substantiate each claim,
                adjusted for whether the sources agree, conflict, or only partly cover it
  reliability - publisher authority, primary-source status, evidence quality and recency
"""
import math
import re
from datetime import date, datetime
from urllib.parse import urlparse

import numpy as np

WEIGHTS = {"relevance": 0.45, "reliability": 0.30, "quantity": 0.25}

# bge-small-en-v1.5 cosine ranges, mapped onto 0..1
QUESTION_FLOOR, QUESTION_CEIL = 0.45, 0.80   # question vs passage
CLAIM_FLOOR, CLAIM_CEIL = 0.45, 0.72         # answer claim vs passage
SUPPORT_THRESHOLD = 0.58                     # claim counts as backed by a passage

SAME_PUBLISHER_WEIGHT = 0.35   # extra pages from one publisher are not independent
QUANTITY_SCALE = 1.5           # 1 strong source ~0.49, 2 ~0.74, 3 ~0.86

AGREEMENT_FACTOR = {"agree": 1.0, "partial": 0.85, "conflict": 0.6}
AGREEMENT_TEXT = {
    "agree": "the sources agree",
    "partial": "the sources only partly cover this",
    "conflict": "the sources disagree",
}
HIGH, MEDIUM = 75, 50
NO_GROUNDING_CAP, CONFLICT_CAP = 30, 60

TRUSTED_NONPROFITS = {"ncoa.org", "aarp.org", "bbb.org", "consumerreports.org"}

# Publishers that are the primary authority when the question is about their topic
PRIMARY_TOPICS = {
    "irs.gov": ("irs", "tax", "taxes", "refund"),
    "ssa.gov": ("social security", "ssa"),
    "medicare.gov": ("medicare",),
    "cms.gov": ("medicare", "medicaid"),
    "consumerfinance.gov": ("cfpb", "bank", "loan", "credit", "debt", "mortgage"),
    "ic3.gov": ("fbi", "internet crime", "online", "crypto", "cryptocurrency"),
    "ojp.gov": ("elder fraud", "victim", "hotline"),
    "ftc.gov": ("ftc", "identity theft", "robocall"),
}

LEVEL_SUMMARY = {
    "high": "Trusted sources clearly back this answer.",
    "medium": "Trusted sources back parts of this answer. Some details may be missing.",
    "low": "This answer has limited support from my sources. Double-check before acting.",
    "none": "None of my trusted sources covered this, so I can't rate this answer.",
}

_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_AGREEMENT_LINE = re.compile(r"^\s*source check:\s*(agree|partial|conflict)\b.*$", re.I | re.M)


def cited_numbers(text):
    """All citation numbers in text, handling [1], [1][2] and [1, 2]."""
    return {int(n) for group in _CITE.findall(text) for n in group.split(",")}


def split_agreement(text):
    """Remove the model's 'Source check: ...' line; return (clean_text, label or None)."""
    m = _AGREEMENT_LINE.search(text)
    if not m:
        return text, None
    return _AGREEMENT_LINE.sub("", text).strip(), m.group(1).lower()


def extract_claims(text):
    """Bullet points (or sentences as a fallback) paired with the source numbers they cite."""
    lines = [ln.strip() for ln in text.splitlines()]
    pieces = [ln.lstrip("-*• ").strip() for ln in lines if ln.startswith(("-", "*", "•"))]
    if not pieces:
        body = " ".join(ln for ln in lines if ln and not ln.endswith(":"))
        pieces = re.split(r"(?<=[.!?])\s+", body)
    claims = []
    for piece in pieces:
        plain = re.sub(rf"\s*{_CITE.pattern}", "", piece).strip()
        if re.search(r"[A-Za-z]{3}", plain):
            claims.append((plain, cited_numbers(piece)))
    return claims


def _scale(x, lo, hi):
    return float(min(1.0, max(0.0, (x - lo) / (hi - lo))))


def _unit(rows):
    m = np.array(rows, dtype=float)
    if m.ndim == 1:
        m = m[None, :]
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)


def _domain(url):
    host = (urlparse(url).hostname or "").lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _mentions(question, keywords):
    q = question.lower()
    return any(re.search(rf"\b{re.escape(k)}\b", q) for k in keywords)


def source_reliability(source, question, passage="", today=None):
    """Return (score 0..1, authority label, reasons) for one source."""
    today = today or date.today()
    domain = _domain(source.url)
    reasons = []

    if domain.endswith((".gov", ".mil")):
        score, label = 1.0, "Official government source"
    elif domain.endswith(".edu"):
        score, label = 0.85, "Academic source"
    elif domain in TRUSTED_NONPROFITS:
        score, label = 0.8, "Established nonprofit"
    elif domain.endswith(".org"):
        score, label = 0.6, "Organization website"
    else:
        score, label = 0.45, "Unverified publisher"

    if _mentions(question, PRIMARY_TOPICS.get(domain, ())):
        score = min(1.0, score + 0.1)
        reasons.append("primary authority on this topic")

    if "/archive/" in source.url.lower():
        score *= 0.85
        reasons.append("archived page, may be out of date")
    if passage and len(passage.split()) < 40:
        score *= 0.9
        reasons.append("short passage with little detail")

    reviewed = source.last_reviewed or source.last_ingested
    if isinstance(reviewed, datetime):
        reviewed = reviewed.date()
    if isinstance(reviewed, date):
        years = (today - reviewed).days / 365
        if years > 1:
            score *= max(0.6, 1 - 0.2 * (years - 1))
            reasons.append(f"last reviewed {int(years)} year(s) ago")
    else:
        score *= 0.85
        reasons.append("review date unknown")

    return score, label, reasons


def no_support():
    return {
        "score": 0, "level": "none", "summary": LEVEL_SUMMARY["none"],
        "agreement": None, "factors": None, "notes": [],
    }


def assess(question, answer, hits, embed, agreement=None, today=None):
    """Score an answer.

    hits:  [(chunk, retrieval_score)] in the order they were numbered in the prompt.
    embed: callable mapping a list of strings to a list of vectors (same model as chunks).
    agreement: the model's own 'agree' / 'partial' / 'conflict' label, if it gave one.

    Returns (confidence dict, per-hit details list aligned with hits).
    """
    if not hits:
        return no_support(), []
    claims = extract_claims(answer)
    if not claims:
        return no_support(), [{"supports": False} for _ in hits]

    n = len(hits)
    passages = _unit([c.embedding for c, _ in hits])
    claim_vecs = _unit(list(embed([text for text, _ in claims])))
    sim = claim_vecs @ passages.T   # claims x passages

    # Relevance and alignment
    claim_support, grounded = [], 0
    for i, (_, cites) in enumerate(claims):
        idx = [k - 1 for k in cites if 1 <= k <= n]
        best = float(sim[i, idx].max()) if idx else 0.0
        claim_support.append(_scale(best, CLAIM_FLOOR, CLAIM_CEIL) if idx else 0.0)
        grounded += best >= SUPPORT_THRESHOLD
    grounding = sum(claim_support) / len(claims)
    grounded_frac = grounded / len(claims)

    used = sorted({k - 1 for _, cites in claims for k in cites if 1 <= k <= n}) or list(range(n))
    question_fit = sum(_scale(hits[j][1], QUESTION_FLOOR, QUESTION_CEIL) for j in used) / len(used)

    inferred = "agree" if grounded_frac >= 0.6 else "partial"
    if agreement not in AGREEMENT_FACTOR:
        agreement = inferred
    elif agreement == "agree" and inferred == "partial":
        agreement = "partial"   # the model says the sources agree, but they don't back most claims
    relevance = (0.35 * question_fit + 0.65 * grounding) * AGREEMENT_FACTOR[agreement]

    # Source quantity: independent publishers whose passages back at least one claim
    strength = [_scale(float(sim[:, j].max()), CLAIM_FLOOR, CLAIM_CEIL)
                if sim[:, j].max() >= SUPPORT_THRESHOLD else 0.0 for j in range(n)]
    per_source = {}
    for j, (c, _) in enumerate(hits):
        if strength[j] > per_source.get(c.source_id, (None, 0.0))[1]:
            per_source[c.source_id] = (j, strength[j])
    by_domain = {}
    for j, s in per_source.values():
        by_domain.setdefault(_domain(hits[j][0].source.url), []).append((s, j))
    effective = 0.0
    for group in by_domain.values():
        group.sort(reverse=True)
        effective += group[0][0] + SAME_PUBLISHER_WEIGHT * sum(s for s, _ in group[1:])
    quantity = 1 - math.exp(-effective / QUANTITY_SCALE)

    # Source reliability, weighted by how much each passage contributes
    details, rel_scores = [], []
    for j, (c, _) in enumerate(hits):
        score, label, reasons = source_reliability(c.source, question, c.text, today)
        rel_scores.append(score)
        details.append({
            "supports": strength[j] > 0,
            "reliability": round(score * 100),
            "authority": label,
            "reliability_notes": reasons,
        })
    weights = [strength[j] for j in range(n)]
    if not any(weights):
        weights = [1.0 if j in used else 0.0 for j in range(n)]
    reliability = sum(w * r for w, r in zip(weights, rel_scores)) / sum(weights)

    score = 100 * (WEIGHTS["relevance"] * relevance
                   + WEIGHTS["reliability"] * reliability
                   + WEIGHTS["quantity"] * quantity)
    notes = []
    if grounded == 0:
        score = min(score, NO_GROUNDING_CAP)
        notes.append("None of the answer's points closely match the passages they cite.")
    elif grounded_frac < 1:
        missing = len(claims) - grounded
        notes.append(f"Not clearly backed by a source: {missing} of {len(claims)} points in the answer.")
    if agreement == "conflict":
        score = min(score, CONFLICT_CAP)
        notes.append("The sources disagree with each other on some points.")
    elif agreement == "partial":
        notes.append("The sources only cover part of this message.")
    score = round(score)
    level = "high" if score >= HIGH else "medium" if score >= MEDIUM else "low"

    publishers = [hits[g[0][1]][0].source.publisher for g in by_domain.values() if g[0][0] > 0]
    supporting = sum(1 for g in by_domain.values() if g[0][0] > 0)
    quantity_detail = (", ".join(publishers) + "." if publishers
                       else "No source clearly backs the answer's points.")
    labels = sorted({d["authority"] for d, w in zip(details, weights) if w > 0})

    return {
        "score": score,
        "level": level,
        "summary": LEVEL_SUMMARY[level],
        "agreement": agreement,
        "factors": {
            "quantity": {"count": supporting, "detail": quantity_detail},
            "relevance": {
                "score": round(relevance * 100),
                "detail": f"{grounded} of {len(claims)} points match the cited passages; "
                          f"{AGREEMENT_TEXT[agreement]}.",
            },
            "reliability": {
                "score": round(reliability * 100),
                "detail": "Mostly from: " + ", ".join(labels) + ".",
            },
        },
        "notes": notes,
    }, details
