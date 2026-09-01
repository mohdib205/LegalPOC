# Project Overview

## What NyayaSetu Is
NyayaSetu is an offline, AI-powered legal research tool tailored for Indian law. It operates locally, ensuring privacy and zero cloud API costs.

## The Problem It Solves
Standard AI language models frequently hallucinate legal citations, creating fake case laws that look authentic. NyayaSetu solves this by forcing the AI to cite sources from a verified local database, actively verifying these citations before presenting them to the user.

## POC Scope
This Proof of Concept (POC) focuses strictly on **Section 138 of the Negotiable Instruments Act, 1881** (cheque dishonour/bounce cases). It operates on a small, hand-curated dataset (20-40 judgments) and runs entirely on a standard 16GB laptop without a GPU.

## What Makes NyayaSetu Different
**Citation Verification:** The system intercepts the AI's response and checks every single case ID cited against the local database. If a case isn't in the database, it's flagged as unverified (⚠️). Verified citations are marked clearly (✅).

## Main Technologies
- **Python**
- **SQLite** (Storage & Keyword Search)
- **ChromaDB** (Vector Search)
- **Ollama** (Local LLM Execution - Phi-3 Mini / Llama 3.1)
- **Streamlit** (Web UI)
- **sentence-transformers** (Embeddings)

## Simple Request Lifecycle
1. **Question**: User asks a legal question in the UI.
2. **Hybrid Search**: System searches both ChromaDB (meaning) and SQLite (exact keywords).
3. **Local LLM**: An offline model writes an answer using only the searched cases, embedding `[CASE: id]` tags.
4. **Citation Verifier**: The system checks the tags against SQLite.
5. **Answer**: User sees the final answer with verified/unverified markers.

## Simple Project Structure
- `data/`: Raw judgment JSONs.
- `db/`: The local SQLite and ChromaDB databases.
- `src/`: Core Python scripts (ingestion, search, verification, app).

## Intentionally Not Part of this POC
- Drafting legal documents
- Chat history/memory
- Docker or cloud deployment
- Fine-tuning models
