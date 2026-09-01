"""Hybrid search: semantic (ChromaDB) + keyword (SQLite FTS5)."""
import os
import chromadb
from chromadb.utils import embedding_functions
from db import search_keyword

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "chroma")
COLLECTION_NAME = "judgments"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        _collection = _client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
    return _collection


def semantic_search(query: str, top_k: int = 5, threshold: float = 0.55):
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=top_k)
    hits = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        score = 1 - dist
        if score >= threshold:
            hits.append({
                "case_id": meta["case_id"], "title": meta["title"], "court": meta["court"],
                "date": meta["date"], "section": meta["section"], "text": doc,
                "score": score, "source": "semantic",
            })
    return hits


def hybrid_search(query: str, top_k: int = 5):
    semantic_hits = semantic_search(query, top_k=top_k)
    keyword_hits = search_keyword(query, limit=top_k)

    seen_case_ids = {h["case_id"] for h in semantic_hits}
    merged = list(semantic_hits)

    for kh in keyword_hits:
        if kh["case_id"] not in seen_case_ids:
            merged.append({
                "case_id": kh["case_id"], "title": kh["title"], "court": kh["court"],
                "date": kh["date"], "section": "keyword_match", "text": "",
                "score": None, "source": "keyword",
            })
            seen_case_ids.add(kh["case_id"])

    return merged[:top_k]