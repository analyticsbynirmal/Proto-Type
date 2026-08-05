"""
Evidence retrieval: for a given claim, first check the local vector DB
cache; if not enough cached evidence is found, query PubMed live via the
free NCBI E-utilities API (no key required, rate-limited to 3 req/sec),
then cache the new results for future reuse.
"""

import requests
import time
import logging
from vector_store import query_cached_evidence, store_evidence

logger = logging.getLogger("medverify.evidence_retrieval")

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

_REQUEST_DELAY = 0.34  # ~3 requests/sec, free-tier rate limit


def _pubmed_search(query: str, max_results: int = 5) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }
    resp = requests.get(ESEARCH_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("esearchresult", {}).get("idlist", [])


def _pubmed_fetch_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    resp = requests.get(EFETCH_URL, params=params, timeout=15)
    resp.raise_for_status()

    # Lightweight XML parse (avoids extra deps)
    import xml.etree.ElementTree as ET
    root = ET.fromstring(resp.content)

    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else None

        title_el = article.find(".//ArticleTitle")
        title = title_el.text if title_el is not None else ""

        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join(a.text for a in abstract_parts if a.text)

        text = f"{title}. {abstract}".strip()
        if pmid and text and len(text) > 20:
            articles.append({"text": text, "pmid": pmid, "source": "PubMed"})

    return articles


def retrieve_evidence(claim: str, max_results: int = 5) -> list[dict]:
    """
    Returns a list of evidence dicts: {text, pmid, source, similarity?, cached}
    """
    cached = query_cached_evidence(claim, n_results=max_results)
    if len(cached) >= 3:
        logger.info("Using %d cached evidence item(s) for claim.", len(cached))
        return cached

    try:
        pmids = _pubmed_search(claim, max_results=max_results)
        time.sleep(_REQUEST_DELAY)
        fresh = _pubmed_fetch_abstracts(pmids)
    except requests.RequestException as e:
        logger.error("PubMed API error: %s", e)
        return cached  # fall back to whatever cache we had, even if thin

    if fresh:
        store_evidence(fresh)

    # Merge cache + fresh, de-duplicate by pmid
    seen = {item["pmid"] for item in cached}
    merged = cached + [f for f in fresh if f["pmid"] not in seen]
    return merged
