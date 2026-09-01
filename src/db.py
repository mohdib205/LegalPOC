"""
Database layer for NyayaSetu MVP.

Uses SQLite by default so the whole MVP runs with zero external services.
To move to PostgreSQL later (for real tsvector full-text search and concurrent
access), change DB_URL below to something like:
    postgresql://user:pass@localhost:5432/nyayasetu
and swap the FTS query in search_keyword() for a real tsvector query.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "nyayasetu.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    court TEXT,
    date TEXT,
    judges TEXT,          -- comma-separated for MVP simplicity
    full_text TEXT NOT NULL
);

-- SQLite full-text search virtual table (stands in for Postgres tsvector)
CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(
    case_id UNINDEXED,
    title,
    court UNINDEXED,
    date UNINDEXED,
    judges UNINDEXED,
    full_text,
    content='cases',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS citations (
    citing_case_id TEXT NOT NULL,
    cited_case_id TEXT NOT NULL,
    FOREIGN KEY (citing_case_id) REFERENCES cases(case_id),
    FOREIGN KEY (cited_case_id) REFERENCES cases(case_id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    answer TEXT,
    rating TEXT,           -- 'up' or 'down'
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def case_exists(case_id: str) -> bool:
    """Core function used by the citation verifier — is this case ID real?"""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM cases WHERE case_id = ?", (case_id,)
    ).fetchone()
    conn.close()
    return row is not None


def get_case(case_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM cases WHERE case_id = ?", (case_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def search_keyword(query: str, limit: int = 5):
    """Keyword half of hybrid search, using SQLite FTS5 (Postgres tsvector equivalent)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT cases.case_id, cases.title, cases.court, cases.date
            FROM cases_fts
            JOIN cases ON cases.case_id = cases_fts.case_id
            WHERE cases_fts MATCH ?
            LIMIT ?
            """,
            (query, limit)
        ).fetchall()
        
        hits = []
        for r in rows:
            hits.append({
                "case_id": r[0], "title": r[1], "court": r[2], "date": r[3]
            })
        return hits
    except sqlite3.OperationalError:
        # FTS query syntax error (e.g. special characters) - fail soft
        return []
    finally:
        conn.close()
