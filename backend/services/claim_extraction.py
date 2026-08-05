"""
Claim extraction: segment an LLM response into sentences, then keep only
sentences that contain a medical entity (scispaCy NER). This discards
greetings, hedges, and disclaimers per the project spec (Phase 1).
"""

import spacy
import logging

logger = logging.getLogger("medverify.claim_extraction")

_nlp = None
_MODEL_NAME = "en_core_sci_sm"  # scispaCy small biomedical model
_FALLBACK_MODEL = "en_core_web_sm"  # used only if scispaCy model isn't installed


def _load_model():
    global _nlp
    if _nlp is not None:
        return _nlp
    try:
        _nlp = spacy.load(_MODEL_NAME)
        logger.info(f"Loaded scispaCy model: {_MODEL_NAME}")
    except OSError:
        logger.warning(
            f"'{_MODEL_NAME}' not found. Falling back to '{_FALLBACK_MODEL}'. "
            f"Install scispaCy model for real medical NER: see requirements.txt."
        )
        _nlp = spacy.load(_FALLBACK_MODEL)
    return _nlp


# Minimal hedge/greeting patterns as a second filter layer (cheap, no model needed)
_SKIP_PATTERNS = [
    "i'm not a doctor", "consult a doctor", "consult your doctor",
    "this is not medical advice", "i am an ai", "as an ai",
    "hello", "hi there", "hope this helps", "let me know if",
    "happy to help", "i understand", "i'm sorry", "disclaimer",
]


def _looks_like_hedge(sentence: str) -> bool:
    s = sentence.lower().strip()
    if len(s) < 8:
        return True
    return any(p in s for p in _SKIP_PATTERNS)


def extract_claims(text: str) -> list[dict]:
    """
    Returns a list of dicts: {"text": sentence, "entities": [...]}
    Only sentences containing at least one detected entity (scispaCy NER,
    or noun-chunk heuristic if using the fallback model) are kept.
    """
    nlp = _load_model()
    doc = nlp(text)

    claims = []
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text or _looks_like_hedge(sent_text):
            continue

        sent_doc = nlp(sent_text)
        entities = [ent.text for ent in sent_doc.ents]

        # scispaCy model tags biomedical entities directly. If we fell back
        # to a generic model (no biomedical NER), use entity presence OR
        # sentence length as a looser factuality heuristic.
        has_entity = len(entities) > 0
        if has_entity or (nlp.meta.get("name") != _MODEL_NAME and len(sent_text.split()) > 6):
            claims.append({"text": sent_text, "entities": entities})

    return claims
