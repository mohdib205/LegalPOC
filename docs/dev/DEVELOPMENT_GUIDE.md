# NyayaSetu Development Guide

## Environment Setup
1. Create a virtual environment: `python -m venv venv`
2. Activate it: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
3. Install dependencies: `pip install -r requirements.txt`
4. Set up the `.env` file (copy from `.env.example`).
   - `GROQ_API_KEY`: Required for fast cloud inference.
   - `USE_GROQ`: Set to `true` to use Groq, `false` to fallback to local Ollama.

## Running the Application
```bash
python -m streamlit run src/app.py
```
*Note: Due to Streamlit's architecture, ML models and ChromaDB are cached via `@st.cache_resource`. If you modify ingestion or embedding code, you must restart the Streamlit server to clear the cache.*

## Testing & Evaluation

### UI Testing
To bypass Streamlit's thread management during rapid testing, use:
```bash
python tools/testing/run_ui_test_cached.py
```

### RAG Evaluation Suite
We have a robust Q1-Q15 evaluation suite to detect regressions in citation mapping and retrieval.
```bash
python tools/evaluation/evaluate_rag.py
```
This script will dump structured JSON files into `data/evaluation/run_<timestamp>/results` evaluating correctness and mapping.

## Code Standards
- **Instrument Everything**: Wrap major pipeline steps with `instrumentation.start()` and `instrumentation.end()` to track latencies.
- **Strict Citations**: Never allow the LLM to format `[CASE: id]` tokens. Use the deterministic Python citation mapper in `rag_chain.py` to extract `case_id` securely from the ChromaDB metadata payload.
- **Do not modify `.env` loading**: Streamlit natively loads `.env` at the top of `app.py`.
