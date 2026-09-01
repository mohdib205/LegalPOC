# AI Working Rules for NyayaSetu POC

Future AI tools and coding assistants must strictly adhere to the following rules when interacting with this codebase:

## General Rules
- Read the relevant documentation in `docs/ai/` before making changes.
- Inspect existing code before rewriting functionality.
- Do not introduce new frameworks, dependencies, or libraries unless absolutely necessary.
- Do not change the core POC architecture without explicit approval from the user.
- Do not replace SQLite, ChromaDB, Ollama, or Streamlit without explicit approval.
- Prefer small targeted changes over large rewrites.
- If user requirements conflict with the current implementation, explain the conflict instead of silently changing the architecture.

## Scope Rules
- Do NOT add Phase 2 features to the POC (e.g., Docker, fine-tuning, multi-turn memory, auth, drafting).
- Preserve the current separation of responsibilities between modules as defined in `ARCHITECTURE.md`.

## Citation and Verification Rules (CRITICAL)
- Keep all LLM citations strictly verifiable.
- Never allow a citation to be displayed as verified without explicit database validation via `citation_verifier.py` and `db.py`.
- The system must prioritize citation reliability over eloquent answers. Hallucination prevention is the core value proposition.

## Configuration and Secrets
- Do not hardcode secrets or API keys in the code.
- Do not modify `.env` files programmatically or assume `.env` structures beyond what is standard.

## Documentation Maintenance
- Update `CURRENT_STATUS.md` when completing major project work.
- Update relevant documentation (`PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `DEVELOPMENT_GUIDE.md`) when the architecture or workflow changes.
