# NyayaSetu MVP — Offline Indian Legal AI (Week 1 POC)

A local, offline RAG pipeline for Indian legal Q&A with strict zero-hallucination citation verification.
Domain in this POC: **Section 138 Negotiable Instruments Act (cheque bounce) cases**.

## Architecture (V2)

```
Query
  │
  ▼
Hybrid Search (ChromaDB semantic + SQLite FTS5 keyword)
  │
  ▼
LangChain prompt assembly (top-k chunks + query)
  │
  ▼
LLM Generation (Groq qwen3.6-27b [Primary] OR Local Ollama [Fallback])
  │
  ▼
Deterministic Python Citation Mapping (Extracts case_id from ChromaDB metadata)
  │
  ▼
Citation Verifier (checks every case ID against the SQLite DB)
  │
  ▼
Streamlit UI (shows verified vs. unverified citations separately)
```

## Why this order matters

An AI legal answer is only as good as (a) whether the right judgment was retrieved and (b) whether the citation it produced actually exists. In V2, we removed the burden of formatting from the LLM. The LLM generates a JSON array of `evidence_quotes`. Python deterministically string-matches these quotes against the retrieved chunks and extracts the authoritative `case_id` directly from the ChromaDB metadata payload. The verifier in `src/citation_verifier.py` then acts as the final gatekeeper against hallucinations.

## Setup

The repository comes pre-populated with a dataset in `db/nyayasetu.db` and `db/chroma/`. You do not need to re-ingest data to run the app.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure Environment
# Copy .env.example to .env
# Set GROQ_API_KEY for fast cloud inference (~2s)
# OR set USE_GROQ=false to use local fallback (requires Ollama)

# 3. Run the application
streamlit run src/app.py
```

*Note: If using local fallback, make sure to install Ollama and run `ollama pull llama3.1:8b` first.*

## Adding New Data

If you wish to add more judgments, use the offline ingestion pipeline:

```json
// shape of data/sample_judgments/*.json
{
  "case_id": "NI138-2019-0042",
  "title": "Rajesh Kumar v. State Bank of India",
  "court": "Delhi High Court",
  "date": "2019-06-14",
  "judges": ["Justice A. Sharma"],
  "full_text": "..."
}
```

```bash
# Initialize DB (if starting fresh)
python src/init_db.py

# Ingest new judgments
python src/ingest.py --input data/sample_judgments/

# Build embeddings
python src/chunk_embed.py
```

## What's NOT in this MVP

OCR, citation graph, LoRA fine-tuning, drafting mode, multi-turn memory, Hindi/Whisper support, Docker. Get this working end-to-end first.

## Folder structure

```
nyayasetu/
├── src/                      # PRIMARY APPLICATION (Git-tracked)
│   ├── app.py                # Streamlit UI
│   ├── rag_chain.py          # RAG pipeline orchestration (Groq/Ollama branching)
│   ├── search.py             # Hybrid retrieval logic (@st.cache_resource)
│   ├── citation_verifier.py  # Validation of LLM citations
│   ├── db.py                 # SQLite configuration
│   ├── chunk_embed.py        # Offline embedding logic
│   ├── ingest.py             # Offline data ingestion
│   ├── fetch_judgments.py    # Offline scraper 
│   └── kanoon_client.py      # Indian Kanoon API client
│
├── data/                     # RUNTIME DATA
│   ├── scraped_judgments/    # Raw JSON judgments
│   └── case_lists/           # Original search queries
│
├── db/                       # PRE-POPULATED DATABASE
│   ├── nyayasetu.db          # SQLite structured metadata and FTS5 index
│   └── chroma/               # ChromaDB semantic vector index
│
└── docs/                     # DOCUMENTATION
    ├── ai/                   # AI architecture & status
    └── dev/                  # Developer guides
```
