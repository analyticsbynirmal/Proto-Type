"""
MedVerify backend - FastAPI local server.

Pipeline (per Phase 0/1 scope):
  full LLM response text
    -> claim extraction (sentence split + scispaCy medical NER filter)
    -> for each claim: evidence retrieval (vector DB cache -> PubMed live)
    -> NLI verification (PubMedBERT-MedNLI) ranked by entailment score
    -> trust score (simplified formula)
    -> verdict: Supported / Contradicted / No Evidence

Run with:
    uvicorn main:app --reload --port 8008
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.claim_extraction import extract_claims
from services.evidence_retrieval import retrieve_evidence
from services.nli_verification import verify_claim_against_evidence
from services.trust_score import compute_trust_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medverify.main")

app = FastAPI(title="MedVerify Backend", version="0.1.0")

# Chrome extensions call from an "chrome-extension://" origin; allow all for local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class VerifyRequest(BaseModel):
    text: str
    max_claims: int = 8          # cap for MVP responsiveness
    evidence_per_claim: int = 5


class ClaimResult(BaseModel):
    claim: str
    verdict: str
    trust_score: float
    evidence: list


class VerifyResponse(BaseModel):
    total_sentences_seen: int
    claims_checked: int
    results: list[ClaimResult]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest):
    claims = extract_claims(req.text)
    claims_to_check = claims[: req.max_claims]

    results = []
    for c in claims_to_check:
        claim_text = c["text"]
        logger.info("Verifying claim: %s", claim_text)

        evidence = retrieve_evidence(claim_text, max_results=req.evidence_per_claim)
        if not evidence:
            results.append(ClaimResult(
                claim=claim_text, verdict="No Evidence Found", trust_score=0.0, evidence=[]
            ))
            continue

        ranked = verify_claim_against_evidence(claim_text, evidence)
        scored = compute_trust_score(ranked)

        results.append(ClaimResult(
            claim=claim_text,
            verdict=scored["verdict"],
            trust_score=scored["trust_score"],
            evidence=ranked[:3],  # top 3 evidence items for the UI
        ))

    return VerifyResponse(
        total_sentences_seen=len(claims),
        claims_checked=len(claims_to_check),
        results=results,
    )
