"""
Chunk judgments and build the ChromaDB vector index.
Run after ingest.py: python chunk_embed.py
"""
import os
import re
import chromadb
from chromadb.utils import embedding_functions
from db import get_connection

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "chroma")
COLLECTION_NAME = "judgments"
SECTION_MARKERS = ["FACTS:", "ISSUE:", "REASONING:", "HOLDING:"]


def chunk_by_legal_sections(text: str):
    pattern = "(" + "|".join(re.escape(m) for m in SECTION_MARKERS) + ")"
    parts = re.split(pattern, text)
    if len(parts) <= 1:
        return None

    chunks = []
    current_label = None
    current_text = ""
    for part in parts:
        if part in SECTION_MARKERS:
            if current_text.strip():
                chunks.append((current_label, current_text.strip()))
            current_label = part.rstrip(":")
            current_text = ""
        else:
            current_text += part
    if current_text.strip():
        chunks.append((current_label, current_text.strip()))
    return chunks


def chunk_by_paragraph(text: str, target_size=1200, overlap=150):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + target_size, len(text))
        chunks.append((None, text[start:end]))
        start += target_size - overlap
    return chunks


def build_index():
    conn = get_connection()
    cases = conn.execute("SELECT case_id, title, court, date, full_text FROM cases").fetchall()
    conn.close()

    if not cases:
        print("No cases found. Run ingest.py first.")
        return

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(name=COLLECTION_NAME, embedding_function=embed_fn)

    ids, documents, metadatas = [], [], []
    for case in cases:
        sections = chunk_by_legal_sections(case["full_text"])
        if sections is None:
            sections = chunk_by_paragraph(case["full_text"])

        final_sections = []
        for label, chunk_text in sections:
            if len(chunk_text) > 1200:
                sub_chunks = chunk_by_paragraph(chunk_text)
                for _, sub_text in sub_chunks:
                    final_sections.append((label, sub_text))
            else:
                final_sections.append((label, chunk_text))

        for i, (label, chunk_text) in enumerate(final_sections):
            if not chunk_text.strip():
                continue
            chunk_id_str = f"{case['case_id']}_chunk{i}"
            ids.append(chunk_id_str)
            documents.append(chunk_text)
            metadatas.append({
                "case_id": case["case_id"], "title": case["title"],
                "court": case["court"] or "", "date": case["date"] or "",
                "section": label or "general", "chunk_id": chunk_id_str,
            })

    if ids:
        batch_size = 1000
        total_batches = (len(ids) + batch_size - 1) // batch_size
        for i in range(total_batches):
            start = i * batch_size
            end = start + batch_size
            
            collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end]
            )
            print(f"Added batch {i + 1}/{total_batches}")
    print(f"Indexed {len(ids)} chunks from {len(cases)} cases into ChromaDB.")


if __name__ == "__main__":
    build_index()