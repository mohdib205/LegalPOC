# AI Development Changelog

## [V2 Architecture] - 2026-09-03
### Added
- Integrated Groq Cloud API for near-instant (~2s) generation via `qwen/qwen3.6-27b`.
- Deterministic Python Metadata Mapping: `rag_chain.py` now maps `evidence_quote` directly to the retrieved chunk metadata, extracting authoritative `case_id` safely.
- Added `@st.cache_resource` in Streamlit to eliminate the 30s ML model initialization penalty.
- Configured JSON schema enforcement for both Groq and Ollama.

### Removed
- Entirely removed the 48-second `CITATION_REMINDER` retry loop from `rag_chain.py` as it is no longer needed.
- Removed prompt instructions demanding the LLM embed citation tokens inside prose.

### Changed
- Fixed `.env` loading upstream in `app.py` so `USE_GROQ=true` is respected natively.
- Hybrid search deduplication now safely handles multiple chunks returned from the same case.

## [V1 Baseline]
- Initial creation of NyayaSetu RAG MVP.
- Basic hybrid search (ChromaDB + SQLite).
- Strict hallucination verification via `citation_verifier.py`.
