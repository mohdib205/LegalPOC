# NyayaSetu V2 Architecture

## System Flow Diagram

```mermaid
flowchart TD
    UserQuery[User Question] --> UI[Streamlit UI]
    UI --> RagChain[rag_chain.py]
    RagChain --> HybridSearch[search.py]
    
    subgraph Search Layer
        HybridSearch --> Semantic[ChromaDB]
        HybridSearch --> Keyword[SQLite FTS5]
    end
    
    Search Layer --> RagChain
    RagChain --> PromptAssembly[LangChain/Prompt Assembly]
    
    subgraph Generation Layer
        PromptAssembly --> Config{USE_GROQ?}
        Config -- Yes --> Groq[Groq API: qwen/qwen3.6-27b]
        Config -- No --> Ollama[Local Ollama: llama3.1:8b]
    end
    
    Groq --> RawJSON[JSON Response: Answer + Evidence Quotes]
    Ollama --> RawJSON
    
    RawJSON --> DeterministicMapping[Python Metadata Citation Mapping]
    DeterministicMapping --> Verifier[citation_verifier.py]
    Verifier --> Database[(SQLite db.py)]
    Verifier --> CleanAnswer[Verified / Unverified Answer]
    
    CleanAnswer --> UI
```

## Major Architectural Improvements (V2)

1. **Deterministic Citation Mapping**: The LLM is no longer trusted to generate or format `[CASE: id]` tokens. It strictly outputs a JSON object containing an `answer` and an array of `evidence_quote` strings. Python deterministically maps these quotes against the retrieved chunks and extracts the authoritative `case_id` directly from the ChromaDB metadata.
2. **Groq Cloud Integration**: Primary fast pathway via `qwen/qwen3.6-27b` providing ~2-second latency. Fallback pathway remains local Ollama CPU inference.
3. **Streamlit ML Caching**: Heavy ML initialization (HuggingFace SentenceTransformers, ChromaDB) is cached via `@st.cache_resource` to completely eliminate the 30-second cold-start penalty on reruns.
4. **Zero-Retry Pipeline**: The costly 48-second fallback retry loops for bad LLM formatting were entirely removed due to the robustness of the deterministic Python JSON mapping.

## Major Module Responsibilities
- `src/db.py`: Manages SQLite connection, database schema (`cases`, `citations`, `feedback`), and FTS5 search logic.
- `src/init_db.py`: One-off script to create the SQLite DB.
- `src/ingest.py`: Inserts JSON judgment files into the SQLite database.
- `src/chunk_embed.py`: Splits judgment text into chunks and embeds them into ChromaDB. Stores `case_id`, `title`, `court`, `date`, `section`, and `chunk_id` in metadata.
- `src/search.py`: Executes both ChromaDB semantic search and SQLite keyword search, deduplicates, and returns unified top-k results.
- `src/rag_chain.py`: Orchestrates retrieval, builds the prompt, calls Groq/Ollama in JSON mode, and executes the deterministic Python citation mapping.
- `src/citation_verifier.py`: Parses the mapped text, extracts `[CASE: id]` tags, queries `db.py` to verify their existence, and formats the final answer.
- `src/app.py`: The Streamlit frontend providing the chat interface and rendering verified vs unverified citations.
