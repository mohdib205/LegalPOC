import os
import chromadb
from chromadb.utils import embedding_functions
from db import search_keyword
import instrumentation
import streamlit as st

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "chroma")
COLLECTION_NAME = "judgments"

@st.cache_resource
def _get_collection():
    instrumentation.log("ML INIT", "Initializing ChromaDB and ML models (Cold Start)")
    instrumentation.start("Model/DB Cold Start")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
    dur = instrumentation.end("Model/DB Cold Start")
    instrumentation.log("ML INIT", f"Cold Start END: {dur:.3f} sec")
    return collection


def semantic_search(query: str, top_k: int = 5, threshold: float = 0.55):
    collection = _get_collection()
    
    instrumentation.log("4", "Embedding START")
    instrumentation.start("Embedding")
    embed_fn = collection._embedding_function
    embeddings = embed_fn([query])
    dur_embed = instrumentation.end("Embedding")
    instrumentation.log("4", f"Embedding END: {dur_embed:.3f} sec")
    
    instrumentation.log("5", "ChromaDB search START")
    instrumentation.start("ChromaDB search")
    results = collection.query(query_embeddings=embeddings, n_results=top_k)
    hits = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        score = 1 - dist
        if score >= threshold:
            hits.append({
                "case_id": meta["case_id"], "title": meta["title"], "court": meta["court"],
                "date": meta["date"], "section": meta["section"], "text": doc,
                "score": score, "source": "semantic",
            })
    dur_chroma = instrumentation.end("ChromaDB search")
    instrumentation.log("5", f"ChromaDB search END: {dur_chroma:.3f} sec")
    instrumentation.log("5", f"Number of semantic results: {len(hits)}")
    return hits


def hybrid_search(query: str, top_k: int = 5):
    instrumentation.log("3", "Query preprocessing START")
    instrumentation.start("Query preprocessing")
    # minimal preprocessing done implicitly
    dur_prep = instrumentation.end("Query preprocessing")
    instrumentation.log("3", f"Query preprocessing END: {dur_prep:.3f} sec")

    semantic_hits = semantic_search(query, top_k=top_k)
    
    instrumentation.log("6", "FTS5 search START")
    instrumentation.start("FTS5 search")
    keyword_hits = search_keyword(query, limit=top_k)
    dur_fts = instrumentation.end("FTS5 search")
    instrumentation.log("6", f"FTS5 search END: {dur_fts:.3f} sec")
    instrumentation.log("6", f"Number of keyword results: {len(keyword_hits)}")

    instrumentation.log("7", "Hybrid merge START")
    instrumentation.start("Hybrid merge")
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

    final_results = merged[:top_k]
    dur_merge = instrumentation.end("Hybrid merge")
    instrumentation.log("7", f"Hybrid merge END: {dur_merge:.3f} sec")
    instrumentation.log("7", f"Final retrieved results: {len(final_results)}")
    
    for idx, r in enumerate(final_results):
        instrumentation.log("7", f" - Result {idx+1}: {r['case_id']} | {r['title']}")

    return final_results