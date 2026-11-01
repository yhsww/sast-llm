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
    "uma", "used", "when", "where", "ensure", "using",
}

# Focused terminology expansion and trusted taxonomy anchors for common SAST findings.
_DOMAIN_RULES = (
    (r"\bcors\b|cross.origin resource sharing",
     "origin validation permissive cross-domain policy allow origin credentials preflight",
     {"CWE": ("CWE-942",), "WSTG": ("WSTG-CLNT-07", "WSTG-CONF-08")}),
    (r"private key|\bsecret key\b",
     "cryptographic key exposure hardcoded key key management revoke rotate invalidate",
     {"CWE": ("CWE-321", "CWE-324"), "WSTG": ()}),
    (r"\b(password|credential)s?\b",
     "secret hardcoded password embedded credential authentication credential rotation",
     {"CWE": ("CWE-259", "CWE-522", "CWE-798"), "WSTG": ("WSTG-ATHN-02", "WSTG-ATHN-07")}),
    (r"\brevoke\b|\bcompromised\b",
     "compromised exposed secret invalidate rotate replace revoke credential",
     {"CWE": (), "WSTG": ()}),
    (r"regular expression|\bregex\b|\bregexp\b|backtracking|redos",
     "inefficient regular expression complexity catastrophic backtracking ReDoS denial of service",
     {"CWE": ("CWE-1333",), "WSTG": ("WSTG-BUSL-07",)}),
    (r"template",
     "template injection server-side client-side template engine",
     {"CWE": ("CWE-1336",), "WSTG": ("WSTG-INPV-18", "WSTG-CLNT-15")}),
    (r"saniti[sz]|\bxss\b|cross.site scripting|angular",
     "cross-site scripting HTML JavaScript escaping sanitizer bypass DomSanitizer",
     {"CWE": ("CWE-79", "CWE-80", "CWE-83"), "WSTG": ("WSTG-CLNT-02", "WSTG-CLNT-15")}),
    (r"\beval\b|dynamic code|code execution|code injection",
     "dynamic code injection unsafe execution eval injection",
     {"CWE": ("CWE-94", "CWE-95"), "WSTG": ("WSTG-INPV-11", "WSTG-CLNT-02")}),
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9_+-]+", _normalize(text).lower())
    return {word for word in words if len(word) > 2 and word not in _STOP_WORDS}


def _query_profile(query_text: str) -> tuple[str, dict[str, set[str]]]:
    query = _normalize(query_text)
    anchors: dict[str, set[str]] = {"CWE": set(), "WSTG": set()}
    additions = []
    for pattern, expansion, source_ids in _DOMAIN_RULES:
        if re.search(pattern, query, flags=re.IGNORECASE):
            additions.append(expansion)
            for source, ids in source_ids.items():
                anchors[source].update(ids)
    return f"{query} {' '.join(additions)}".strip(), anchors


def _wstg_allowlist(query_text: str) -> set[str] | None:
    """Restrict WSTG context when only one category is defensible or none is direct."""
    query = _normalize(query_text)
    if re.search(
        r"regular expression|\bregex\b|\bregexp\b|backtracking|redos",
        query,
        flags=re.IGNORECASE,
    ):
        return {"WSTG-BUSL-07"}
    if re.search(
        r"private key|\bsecret key\b|\brevoke\b|\bcompromised\b",
        query,
        flags=re.IGNORECASE,
    ):
        return set()
    return None


def _candidate_rows(collection, query: str, source: str, candidate_k: int, anchors: set[str]):
    hits = collection.query(
        query_texts=[query],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances"],
    )
    rows = {}
    ids = (hits.get("ids") or [[]])[0]
    documents = (hits.get("documents") or [[]])[0]
    metadatas = (hits.get("metadatas") or [[]])[0]
    distances = (hits.get("distances") or [[]])[0]
    for i, doc_id in enumerate(ids):
        rows[doc_id] = {
            "id": doc_id,
            "document": documents[i] or "",
            "metadata": metadatas[i] or {},
            "distance": distances[i] if i < len(distances) else 1.0,
        }

    # Add taxonomy anchors even when semantic search omitted the most relevant item.
    existing = set(rows)
    wanted = sorted(anchors - existing)
    if wanted:
        exact = collection.get(
            ids=wanted,
            include=["documents", "metadatas"],
        )
        exact_ids = exact.get("ids") or []
        exact_docs = exact.get("documents") or []
        exact_meta = exact.get("metadatas") or []
        for i, doc_id in enumerate(exact_ids):
            rows[doc_id] = {
                "id": doc_id,
                "document": exact_docs[i] or "",
                "metadata": exact_meta[i] or {},
                "distance": 0.45,
            }
    return rows.values()


def _rank_candidates(rows, source: str, query_text: str, anchors: set[str]):
    query_tokens = _tokens(query_text)
    ranked = []
    for row in rows:
        doc_id = row["id"]
        metadata = row["metadata"]
        title = metadata.get("title") or doc_id
        content = row["document"]
        distance = row["distance"]
        semantic_score = 1.0 / (1.0 + max(float(distance or 0.0), 0.0))
        title_tokens = _tokens(title)
        overlap = len(query_tokens & title_tokens) / len(title_tokens) if title_tokens else 0.0
        anchor_bonus = 0.35 if doc_id in anchors else 0.0
        title_bonus = 0.15 if query_tokens & title_tokens else 0.0
        score = 0.65 * semantic_score + 0.20 * overlap + anchor_bonus + title_bonus
        ranked.append((
            score,
            RetrievedDoc(
                id=doc_id,
                source=source,
                title=title,
                content=content,
            ),
        ))
    return ranked


def query_knowledge(query_text: str) -> list[RetrievedDoc]:
    """Retrieve and rerank CWE/WSTG context using local Chroma; no LLM API calls."""
    query, anchors = _query_profile(query_text)
    wstg_allowlist = _wstg_allowlist(query_text)
    results: list[RetrievedDoc] = []

    for collection, source, configured_k in (
        (_cwe_collection, "CWE", settings.top_k_cwe),
        (_wstg_collection, "WSTG", settings.top_k_wstg),
    ):
        if source == "WSTG" and wstg_allowlist == set():
            continue

        count = collection.count()
        if count == 0:
            continue

        final_k = min(max(int(configured_k), 1), count)
        candidate_k = min(max(final_k * 6, 12), count)
        effective_anchors = anchors[source]
        if source == "WSTG" and wstg_allowlist is not None:
            effective_anchors = set(wstg_allowlist)

        rows = _candidate_rows(
            collection,
            query,
            source,
            candidate_k,
            effective_anchors,
        )
        if source == "WSTG" and wstg_allowlist is not None:
            rows = [row for row in rows if row["id"] in wstg_allowlist]

        ranked = _rank_candidates(rows, source, query, effective_anchors)
        ranked.sort(key=lambda item: item[0], reverse=True)
        results.extend(doc for _, doc in ranked[:final_k])

    return results
