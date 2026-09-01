# NyayaSetu MVP: Full Technical Flow

There are two different kinds of data moving through the system:
1. **Legal data** — judgments, chunks, embeddings, retrieved evidence.
2. **Control/instruction data** — prompts, model options, citation rules, thresholds.

They meet at the Ollama call.

---

## 1. The Complete Architecture

Think of NyayaSetu as six layers:

```text
┌──────────────────────────────────────────────┐
│                  STREAMLIT                   │
│                  app.py                      │
│                                              │
│ User enters question                         │
└──────────────────────┬───────────────────────┘
                       │
                       │ question: str
                       ▼
┌──────────────────────────────────────────────┐
│                ORCHESTRATION                 │
│                rag_chain.py                  │
│                                              │
│ Coordinates the whole RAG process            │
└──────────────────────┬───────────────────────┘
                       │
                       │ question
                       ▼
┌──────────────────────────────────────────────┐
│                  RETRIEVAL                   │
│                  search.py                   │
│                                              │
│     Semantic search + Keyword search         │
└───────────────┬─────────────────┬────────────┘
                │                 │
                ▼                 ▼
           ChromaDB            SQLite/FTS5
                │                 │
                └────────┬────────┘
                         │
                         │ hits[]
                         ▼
┌──────────────────────────────────────────────┐
│              CONTEXT BUILDING                │
│                rag_chain.py                  │
│                                              │
│ hits[] → context string                      │
└──────────────────────┬───────────────────────┘
                       │
                       │ instructions + evidence
                       ▼
┌──────────────────────────────────────────────┐
│                  GENERATION                  │
│                  Ollama                      │
│                                              │
│              Local Llama/Phi                 │
└──────────────────────┬───────────────────────┘
                       │
                       │ raw answer
                       ▼
┌──────────────────────────────────────────────┐
│              VERIFICATION                    │
│        rag_chain.py + citation_verifier.py   │
│                                              │
│ Citation → database → evidence               │
└──────────────────────┬───────────────────────┘
                       │
                       │ result dict
                       ▼
┌──────────────────────────────────────────────┐
│                  STREAMLIT                   │
│                  app.py                      │
│                                              │
│ Render answer + citations                    │
└──────────────────────────────────────────────┘
```

But there's a second diagram underneath this—the **Offline Data Preparation** phase:

```text
              OFFLINE DATA PREPARATION

Indian Kanoon
     │
     ▼
fetch_judgments.py
     │
     ▼
JSON / judgment files
     │
     ▼
ingest.py
     │
     ▼
SQLite
     │
     ├──────────────► FTS5
     │
     ▼
chunk_embed.py
     │
     ▼
chunks
     │
     ▼
embedding model
     │
     ▼
ChromaDB
```

The first diagram happens **when somebody asks a question**. The second diagram happened **before anybody asks a question**.

---

## Part I: Offline Data Preparation

This is critical because otherwise ChromaDB looks like magic. Your system does not send an entire 30,000-character judgment directly to the LLM every time. Instead, you prepare it.

### Data Acquisition (`fetch_judgments.py` & `kanoon_client.py`)
Its responsibility is to get judgments from the external source and save them locally.
* `fetch_judgments.py` = "What should I fetch?"
* `kanoon_client.py` = "How do I communicate with Kanoon?"

**Search vs. Fetch:**
* `SEARCH` → returns case IDs / metadata ("Which cases might be relevant?")
* `FETCH` → returns actual judgment text ("Download the actual judgment.")

### Ingestion (`ingest.py` & SQLite)
`ingest.py` takes downloaded judgment JSON files and puts them into SQLite (`db/nyayasetu.db`). SQLite acts as the **structured persistent source of truth**. 
While ChromaDB finds semantically similar text, SQLite answers: *"Give me this exact case."*

SQLite also provides the keyword-search mechanism through **FTS5** (Full Text Search). If a user asks for "Section 138 legal notice", FTS5 catches exact terminology which is crucial for legal research where statutory terms matter.

### Chunking & Embedding (`chunk_embed.py`)
The system splits 25,000-word judgments into smaller chunks (e.g., ~7,325 chunks total). 
* **Why chunks?** If you embed a 30-page judgment, the resulting single vector represents a muddy mixture of facts, arguments, and holdings. By chunking, a relevant legal proposition gets its own precise vector.

Each chunk goes through `all-MiniLM-L6-v2` to become an embedding vector (e.g., `[0.123, -0.827, 0.442, ...]`), encoding semantic relationships.

**ChromaDB** stores these vectors alongside metadata. It serves as your semantic retrieval index.

---

## Part II: The Live Phase

The user opens Streamlit (`app.py`) and types a question. Streamlit doesn't answer the question—it calls `answer_question(query)` from `rag_chain.py`.

### Orchestration (`rag_chain.py`)
This is the pipeline coordinator. It orchestrates:
`question → retrieve → build context → generate → verify → return`

### Retrieval (`search.py`)
`hybrid_search(question, top_k=5)` crosses the file boundary. The question hasn't gone to the LLM yet; the system is just looking for evidence.

* **Semantic Search:** The user query is embedded into a vector. Chroma compares it with stored vectors. 
  * *Distance vs Similarity:* Chroma returns a distance. The app converts it: `similarity = 1 - distance`. 
  * *Threshold:* A similarity threshold of `0.55` is applied. (Relevant chunks scored ~0.60+, irrelevant ones ~0.48-).
* **Keyword Search:** SQLite FTS5 performs exact match retrieval.

Both paths merge into a list of dictionaries called `hits`. 

### Context Assembly
`build_context(hits)` converts the structured Python list of dictionaries into a plain text representation (e.g., `--- case_id: NI138... --- \n The notice was sent...`). This is what the LLM will actually read.

### Generation (Ollama)
The two worlds meet. The input to the LLM consists of:
1. System Instructions
2. Retrieved Evidence
3. User Question

**Ollama** is the engine/runtime; **Llama 3.1 8B** is the model. 
* `temperature = 0` and `seed = 42` ensure determinism.
* The model returns raw text (a Python string) containing the answer and citations.

### Verification (`citation_verifier.py` & Substring matching)
The LLM's answer is **not automatically trusted**. 

1. **Database Verification:** `citation_verifier.py` uses regex to extract the citation (e.g., `[CASE: NI138-123]`) and checks SQLite if it exists. 
2. **Evidence Quote Validation:** Because the model could attach a real case ID to a hallucinated claim, the LLM is forced to output an `evidence_quote`. Python deterministically checks if this exact string exists in the retrieved chunk. 
   * Found? → `VERIFIED`
   * Not Found? → `REJECTED`

If the model fails to produce a citation, a **single retry mechanism** kicks in to request it again without infinite looping.

### Final Result & UI
`answer_question()` returns a final dictionary containing the `raw_answer`, `clean_answer`, `verified` citations, `unverified` citations, and `accuracy_note`. `app.py` simply receives this dictionary and renders it for the user.

---

## 3. Data Transformations 
Understanding how data structures change at every stage is crucial:

1. **User Input:** `str` (*"Is an unclaimed notice valid?"*)
2. **Embedding:** `list of floats` (*[0.13, -0.27, ...]*)
3. **Retrieval Output:** `list[dict]` (*[{"case_id": "...", "score": 0.65}]*)
4. **Context:** `str` (*"--- case_id... The notice..."*)
5. **Ollama Input:** `list[dict]` (*messages with role/content*)
6. **LLM Output:** `str` (*raw generated text*)
7. **Citation Extraction:** `list[str]` (*["NI138-41098537"]*)
8. **Final Result:** `dict` (*returned to Streamlit*)

*(Note: The embedding `[0.123, -0.442, ...]` is not the legal information itself, but an index representation used to find the legal information.)*

---

## 4. The Role of Every File

* `fetch_judgments.py`: "I need these judgments."
* `kanoon_client.py`: "I know how to talk to Kanoon."
* `ingest.py`: "I'll put those judgments into SQLite."
* `db.py`: "I manage the database."
* `chunk_embed.py`: "I'll break judgments into searchable pieces and turn them into vectors."
* `ChromaDB`: "I'll find semantically similar chunks."
* `search.py`: "I'll retrieve evidence using semantic + keyword search."
* `rag_chain.py`: "I'll orchestrate the whole question-answer process."
* `Ollama`: "I'll run the local LLM."
* `citation_verifier.py`: "I'll check whether the model's citations are legitimate."
* `app.py`: "I'll show the result to the user."

---

## 5. Debugging by Layer
Bugs are not random; they correspond to specific architecture layers. To debug effectively, **first identify which layer the failure belongs to:**

* **Kanoon 403 Error:** Data acquisition layer.
* **7,325 > 5,461 Chroma batch:** Indexing layer.
* **Contradictory answers (Stance Mismatch):** Generation layer.
* **Wrong case attached to correct claim:** Citation/evidence layer.
* **Bicycle question producing irrelevant answer:** Retrieval/relevance layer.
* **FTS5 malformed database:** Database/search infrastructure layer.

---

## 6. POC Freeze
The NyayaSetu POC is now frozen. The architecture proves the concept effectively using:
`SQLite/FTS5 + ChromaDB → Hybrid Retrieval → Relevance Threshold → Retrieved Evidence → Local LLM (Ollama) → Citation Generation → Deterministic Validation → Streamlit.`

Additional complexities (rerankers, agents, cross-encoders, multiple LLMs) are unnecessary to prove the core concept and should be reserved for future iterations unconstrained by current hardware limitations.
