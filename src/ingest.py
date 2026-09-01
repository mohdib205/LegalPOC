"""
Ingest judgment JSON files into the database.
Usage: python ingest.py --input ../data/sample_judgments/
"""
import argparse
import json
import os
from db import get_connection, init_db


def ingest_file(conn, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    required = ["case_id", "title", "full_text"]
    missing = [k for k in required if k not in data]
    if missing:
        print(f"  SKIP {filepath}: missing fields {missing}")
        return False

    judges = ", ".join(data.get("judges", []))
    conn.execute(
        """
        INSERT OR REPLACE INTO cases (case_id, title, court, date, judges, full_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (data["case_id"], data["title"], data.get("court", ""),
         data.get("date", ""), judges, data["full_text"]),
    )
    conn.execute(
        "INSERT OR REPLACE INTO cases_fts (case_id, title, full_text) VALUES (?, ?, ?)",
        (data["case_id"], data["title"], data["full_text"]),
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    init_db()
    conn = get_connection()

    files = [f for f in os.listdir(args.input) if f.endswith(".json")]
    print(f"Found {len(files)} files in {args.input}")

    ok = 0
    for fname in files:
        if ingest_file(conn, os.path.join(args.input, fname)):
            ok += 1
    conn.commit()
    conn.close()
    print(f"Ingested {ok}/{len(files)} judgments.")


if __name__ == "__main__":
    main()