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


def query_knowledge(query_text: str) -> list[RetrievedDoc]:
    """Consulta as coleções CWE e WSTG e combina os resultados."""
    results: list[RetrievedDoc] = []

    for collection, source in (
        (_cwe_collection, "CWE"),
        (_wstg_collection, "WSTG"),
    ):
        count = collection.count()
        if count == 0:
            continue

        k = min(
            settings.top_k_cwe if source == "CWE" else settings.top_k_wstg,
            count,
        )

        hits = collection.query(query_texts=[query_text], n_results=k)

        for i, doc_id in enumerate(hits["ids"][0]):
            results.append(
                RetrievedDoc(
                    id=doc_id,
                    source=source,
                    title=hits["metadatas"][0][i].get("title", doc_id),
                    content=hits["documents"][0][i],
                )
            )

    return results