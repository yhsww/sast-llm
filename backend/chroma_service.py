import re
import unicodedata

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from .config import settings
from .retrieved_doc import RetrievedDoc

_embedding_fn = DefaultEmbeddingFunction()
_client = chromadb.PersistentClient(path=settings.chroma_persist_path)
_cwe_collection = _client.get_or_create_collection(
    name=settings.chroma_collection_cwe,
    embedding_function=_embedding_fn,
    metadata={"hnsw:space": "cosine"},
)
_wstg_collection = _client.get_or_create_collection(
    name=settings.chroma_collection_wstg,
    embedding_function=_embedding_fn,
    metadata={"hnsw:space": "cosine"},
)

_STOP_WORDS = {
    "a", "as", "ao", "aos", "com", "da", "das", "de", "do", "dos",
    "e", "em", "for", "here", "is", "make", "me", "na", "nas", "no",
    "nos", "o", "os", "para", "por", "que", "safe", "this", "to", "um",
    "uma", "used", "when", "where",
}

_QUERY_EXPANSIONS = (
    (r"\bcors\b|cross.origin resource sharing", "origin policy allow origin credentials preflight"),
    (r"\b(password|credential)s?\b", "secret hardcoded embedded credential authentication"),
    (r"private key|\bsecret key\b", "cryptographic key compromised revoke rotate invalidate"),
    (r"\brevoke\b|\bcompromised\b", "invalidate rotate replace exposed credential"),
    (r"regular expression|\bregex\b|\bregexp\b", "catastrophic backtracking ReDoS denial of service"),
    (r"template", "template injection server-side client-side"),
    (r"saniti[sz]|\bxss\b|cross.site scripting", "cross-site scripting HTML JavaScript escaping sanitizer bypass"),
    (r"\beval\b|dynamic code|code execution|code injection", "CWE-94 dynamic code injection unsafe execution"),
    (r"\bangular\b", "Angular DomSanitizer bypass security trust HTML XSS"),
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9_+-]+", _normalize(text).lower())
    return {word for word in words if len(word) > 2 and word not in _STOP_WORDS}


def _expand_query(query_text: str) -> str:
    query = _normalize(query_text)
    additions = [
        expansion for pattern, expansion in _QUERY_EXPANSIONS
        if re.search(pattern, query, flags=re.IGNORECASE)
    ]
    return f"{query} {' '.join(additions)}".strip()


def _rank_candidates(hits: dict, source: str, query_text: str) -> list[tuple[float, RetrievedDoc]]:
    ids = (hits.get("ids") or [[]])[0]
    if not ids:
        return []

    documents = (hits.get("documents") or [[]])[0]
    metadatas = (hits.get("metadatas") or [[]])[0]
    distances = (hits.get("distances") or [[]])[0]
    query_tokens = _tokens(query_text)
    ranked = []

    for i, doc_id in enumerate(ids):
        metadata = metadatas[i] or {}
        title = metadata.get("title") or doc_id
        content = documents[i] or ""
        distance = distances[i] if i < len(distances) and distances[i] is not None else 1.0
        semantic_score = 1.0 / (1.0 + max(float(distance), 0.0))
        title_tokens = _tokens(title)
        overlap = len(query_tokens & title_tokens) / len(title_tokens) if title_tokens else 0.0
        score = 0.8 * semantic_score + 0.2 * overlap
        ranked.append((score, RetrievedDoc(id=doc_id, source=source, title=title, content=content)))

    return ranked


def query_knowledge(query_text: str) -> list[RetrievedDoc]:
    """Retrieve CWE/WSTG candidates, expand security terminology, and rerank.

    This function uses the local Chroma index only; it does not call an LLM API.
    """
    query = _expand_query(query_text)
    results: list[RetrievedDoc] = []

    for collection, source, configured_k in (
        (_cwe_collection, "CWE", settings.top_k_cwe),
        (_wstg_collection, "WSTG", settings.top_k_wstg),
    ):
        count = collection.count()
        if count == 0:
            continue

        final_k = min(max(int(configured_k), 1), count)
        candidate_k = min(max(final_k * 4, 8), count)
        hits = collection.query(
            query_texts=[query],
            n_results=candidate_k,
            include=["documents", "metadatas", "distances"],
        )
        ranked = _rank_candidates(hits, source, query)
        ranked.sort(key=lambda item: item[0], reverse=True)
        results.extend(doc for _, doc in ranked[:final_k])

    return results
