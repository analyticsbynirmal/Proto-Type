"""
Trust score: MVP-simplified version of the full paper formula
    Trust = aE + bR + gA + dQ

Phase 0/1 scope only has one source (PubMed) and no evidence-hierarchy
tagging yet, so A (cross-source agreement) and Q (evidence quality tier)
are held at fixed placeholder values. This is documented so it's easy to
extend in Phase 2+ once more sources are added.

    E = evidence support score  -> best NLI entailment probability
    R = source reliability      -> fixed weight for PubMed (peer-reviewed)
    A = cross-source agreement  -> placeholder (1.0, single source for now)
    Q = evidence quality tier   -> placeholder (0.7, "unclassified abstract")
"""

SOURCE_RELIABILITY = {
    "PubMed": 0.9,
}
DEFAULT_RELIABILITY = 0.6

# Weights (alpha, beta, gamma, delta) - tunable later in Phase 4
ALPHA, BETA, GAMMA, DELTA = 0.55, 0.20, 0.10, 0.15

PLACEHOLDER_AGREEMENT = 1.0     # single-source MVP
PLACEHOLDER_QUALITY = 0.7       # abstracts, not tier-classified yet


def compute_trust_score(ranked_evidence: list[dict]) -> dict:
    """
    ranked_evidence: output of verify_claim_against_evidence, sorted by
    entailment probability descending.

    Returns {"trust_score": float 0-1, "verdict": str, "top_evidence": dict|None}
    """
    if not ranked_evidence:
        return {"trust_score": 0.0, "verdict": "No Evidence Found", "top_evidence": None}

    top = ranked_evidence[0]
    E = top["nli_probs"].get("entailment", 0.0)
    contradiction_score = top["nli_probs"].get("contradiction", 0.0)
    R = SOURCE_RELIABILITY.get(top.get("source", ""), DEFAULT_RELIABILITY)

    trust = (ALPHA * E) + (BETA * R) + (GAMMA * PLACEHOLDER_AGREEMENT) + (DELTA * PLACEHOLDER_QUALITY)
    trust = round(min(max(trust, 0.0), 1.0), 4)

    # Phase 0 scope: 3-category verdict (Supported / Contradicted / No Evidence)
    if contradiction_score > 0.5 and contradiction_score > E:
        verdict = "Contradicted"
    elif trust >= 0.6:
        verdict = "Supported"
    else:
        verdict = "No Evidence / Insufficient"

    return {"trust_score": trust, "verdict": verdict, "top_evidence": top}
