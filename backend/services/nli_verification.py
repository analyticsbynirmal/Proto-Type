"""
NLI verification: for each (claim, evidence) pair, classify as
Support / Contradict / Neutral using a biomedical NLI model
fine-tuned on MedNLI (PubMedBERT -> MNLI -> MedNLI). Free, local
inference via Hugging Face transformers, no API key required.
"""

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import logging

logger = logging.getLogger("medverify.nli_verification")

_MODEL_NAME = "pritamdeka/PubMedBERT-MNLI-MedNLI"

_tokenizer = None
_model = None
_label_map = None


def _load_model():
    global _tokenizer, _model, _label_map
    if _model is not None:
        return
    logger.info("Loading NLI model: %s (first run may take a while)", _MODEL_NAME)
    _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME)
    _model = AutoModelForSequenceClassification.from_pretrained(_MODEL_NAME)
    _model.eval()

    # id2label from the model config; normalize to lowercase keys we use downstream
    raw_map = _model.config.id2label
    _label_map = {i: str(label).lower() for i, label in raw_map.items()}
    logger.info("NLI label map: %s", _label_map)


def classify_pair(premise: str, hypothesis: str) -> dict:
    """
    premise = evidence text, hypothesis = claim.
    Returns {"label": "entailment"|"contradiction"|"neutral", "score": float, "probs": {...}}
    """
    _load_model()

    inputs = _tokenizer(premise, hypothesis, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        logits = _model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]

    prob_dict = {_label_map[i]: float(probs[i]) for i in range(len(probs))}
    best_idx = int(torch.argmax(probs))
    return {
        "label": _label_map[best_idx],
        "score": float(probs[best_idx]),
        "probs": prob_dict,
    }


def verify_claim_against_evidence(claim: str, evidence_list: list[dict]) -> list[dict]:
    """
    Runs NLI on each (evidence, claim) pair. Returns evidence_list enriched
    with nli_label and nli_score, sorted by entailment probability desc.
    """
    _load_model()
    enriched = []
    for ev in evidence_list:
        result = classify_pair(premise=ev["text"], hypothesis=claim)
        enriched.append({
            **ev,
            "nli_label": result["label"],
            "nli_score": round(result["score"], 4),
            "nli_probs": {k: round(v, 4) for k, v in result["probs"].items()},
        })

    # Rank by entailment (support) probability, highest first
    def entail_score(item):
        return item["nli_probs"].get("entailment", 0.0)

    enriched.sort(key=entail_score, reverse=True)
    return enriched
