# NyayaSetu Architecture

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
    PromptAssembly --> LLM[Ollama Local LLM]
    LLM --> RawAnswer[Raw Answer with Citations]
    
    RawAnswer --> Verifier[citation_verifier.py]
    Verifier --> Database[(SQLite db.py)]
    Verifier --> CleanAnswer[Verified / Unverified Answer]
    
    CleanAnswer --> UI
```

## Major Module Responsibilities
- `src/db.py`: Manages SQLite connection, database schema (`cases`, `citations`, `feedback`), and keyword search logic.
- `src/init_db.py`: One-off script to create the SQLite DB.
- `src/kanoon_client.py`: Handles HTTP requests and auth to the Indian Kanoon API.
- `src/fetch_judgements.py`: Uses `kanoon_client.py` to search and download JSON judgments.
- `src/ingest.py`: Inserts JSON judgment files into the SQLite database.
- `src/chunk_embed.py`: Splits judgment text into chunks and embeds them into ChromaDB using sentence-transformers.
- `src/search.py`: Executes both ChromaDB semantic search and SQLite keyword search, deduplicates, and returns unified top-k results.
- `src/citation_verifier.py`: Parses the LLM's raw output, extracts `[CASE: id]` tags, queries `db.py` to verify their existence, and formats the final answer.
- `src/rag_chain.py`: The orchestrator. Takes the query, calls search, builds the prompt, invokes Ollama, passes the result to the verifier, and returns the final package.
- `src/app.py`: The Streamlit frontend providing the chat interface and rendering verified vs unverified citations.

## Database Layer
- **SQLite (`db.py`)**: Stores the full text, metadata (title, court, date), and provides Fast Text Search (FTS5) capabilities for keyword searching. Also stores user feedback.
- **ChromaDB**: Acts as the local vector store, holding embeddings for the judgment chunks.

## Data Ingestion Flow
1. API Fetch (`fetch_judgements.py`) → JSON files (`data/sample_judgments/`).
2. SQLite Ingestion (`ingest.py`) → Populates `cases` table.

## Chunking and Embedding Flow
1. Execute `chunk_embed.py`.
2. Reads cases from SQLite.
3. Splits full text into chunks (prioritizing logical markers, falling back to paragraphs).
4. Generates embeddings using `sentence-transformers`.
5. Saves chunks and vectors to ChromaDB.

## Hybrid Search Flow
1. Query sent to `search.py`.
2. Queries ChromaDB for top semantic matches.
3. Queries SQLite FTS5 for top keyword matches.
4. Results are merged, deduplicated by chunk/case ID, and returned.

## RAG Flow
1. `rag_chain.py` receives query and context chunks.
2. Formats a strict prompt instructing the LLM to only use provided context and cite using `[CASE: id]`.
3. Ollama generates the raw text.

## Citation Verification Flow
1. `citation_verifier.py` uses regex to find `[CASE: id]` in the raw text.
2. Looks up each `id` in SQLite.
3. If found, replaces tag with formatted valid citation.
4. If not found, replaces with an "Unverified" warning tag.

## Streamlit UI Flow
1. Displays text input.
2. Calls `rag_chain.py` on submit.
3. Displays the `clean_answer` from the verifier.
4. Renders separate sections outlining verified and unverified citations.
5. Provides buttons for user feedback (thumbs up/down).
