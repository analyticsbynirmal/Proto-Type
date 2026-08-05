"""
Local vector DB (ChromaDB, on-disk, free) used to cache evidence retrieved
from PubMed. Before hitting the PubMed API, we check whether we already
have semantically similar evidence cached — this cuts down repeat calls
for claims that are the same or paraphrased across sessions.
"""

import chromadb
from chromadb.utils import embedding_functions
import logging

logger = logging.getLogger("medverify.vector_store")

_CHROMA_PATH = "./chroma_store"
_COLLECTION_NAME = "pubmed_evidence"

# Biomedical sentence embedding model (also trained on MedNLI/SciNLI),
# free + local via Hugging Face, no API key needed.
_EMBED_MODEL = "pritamdeka/PubMedBERT-mnli-snli-scinli-scitail-mednli-stsb"

_client = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection

    _client = chromadb.PersistentClient(path=_CHROMA_PATH)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=_EMBED_MODEL
    )
    _collection = _client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB collection ready: %s", _COLLECTION_NAME)
    return _collection


def query_cached_evidence(claim: str, n_results: int = 5, min_similarity: float = 0.55):
    """
    Look for cached evidence semantically similar to `claim`.
    Chroma returns cosine *distance*; similarity = 1 - distance.
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[claim], n_results=min(n_results, collection.count()))

    hits = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        similarity = 1 - dist
        if similarity >= min_similarity:
            hits.append({
                "text": doc,
                "pmid": meta.get("pmid"),
                "source": meta.get("source", "PubMed"),
                "similarity": round(similarity, 4),
                "cached": True,
            })
    return hits


def store_evidence(evidence_items: list[dict]):
    """
    evidence_items: list of {"text": str, "pmid": str, "source": str}
    Stored with pmid as the unique id so re-runs don't duplicate entries.
    """
    if not evidence_items:
        return
    collection = get_collection()
    ids = [f"pmid-{item['pmid']}" for item in evidence_items]
    documents = [item["text"] for item in evidence_items]
    metadatas = [{"pmid": item["pmid"], "source": item.get("source", "PubMed")} for item in evidence_items]

    # upsert avoids duplicate-id errors on re-runs
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    logger.info("Cached %d evidence item(s) in vector DB", len(evidence_items))
