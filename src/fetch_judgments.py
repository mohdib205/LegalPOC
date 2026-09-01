"""
Two-step, human-reviewed judgment fetcher.

STEP 1 (see candidates without spending credit on full docs):
    python fetch_judgments.py --step search --query "Section 138 Negotiable Instruments Act dishonour cheque" --court delhi

STEP 2 (fetch full text for the IDs you picked):
    python fetch_judgments.py --step fetch --ids 12345,67890,54321
"""
import argparse
import json
import os
import re
import time
from kanoon_client import search_and_collect, fetch_document

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "scraped_judgments")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def do_search(query, doctypes, max_results, category=None):
    print(f"Searching: {query!r} (doctypes={doctypes})...")
    results = search_and_collect(query, max_results=max_results, doctypes=doctypes)
    print(f"\nFound {len(results)} candidates:\n")
    
    out_lines = []
    for r in results:
        doc_id = r.get("tid", r.get("docid", "?"))
        title = r.get("title", "(no title)")
        source = r.get("docsource", "")
        line = f"{doc_id}  |  {title}  |  {source}"
        print(f"  {line}")
        out_lines.append(line)
        
    if category:
        list_dir = os.path.join(os.path.dirname(__file__), "..", "data", "case_lists")
        os.makedirs(list_dir, exist_ok=True)
        out_file = os.path.join(list_dir, f"{category}_search_results.txt")
        with open(out_file, "a", encoding="utf-8") as f:
            f.write(f"\n# --- SEARCH RESULTS ---\n# QUERY: {query}\n")
            f.write("\n".join(out_lines) + "\n")
        print(f"\nSaved search results to {out_file}")
        print(f"You can copy desired lines into a new file (e.g. data/case_lists/{category}.txt) and run:")
        print(f"  python fetch_judgments.py --step fetch --ids_file data/case_lists/{category}.txt")
    else:
        print(f"\nReview the list, then run:\n"
              f"  python fetch_judgments.py --step fetch --ids <comma-separated ids>")


def do_fetch(ids):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    unique_ids = []
    seen = set()
    for doc_id in ids:
        doc_id = doc_id.strip()
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            unique_ids.append(doc_id)
            
    for doc_id in unique_ids:
        out_path = os.path.join(OUTPUT_DIR, f"case_{doc_id}.json")
        if os.path.exists(out_path):
            print(f"Skipping {doc_id} — already downloaded.")
            continue
            
        print(f"Fetching {doc_id}...")
        try:
            raw = fetch_document(doc_id)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        case = {
            "case_id": f"NI138-{doc_id}",
            "title": raw.get("title", "").strip(),
            "court": raw.get("docsource", "").strip(),
            "date": raw.get("publishdate", "").strip(),
            "judges": [raw.get("author", "").strip()] if raw.get("author") else [],
            "full_text": strip_html(raw.get("doc", "")),
        }

        if not case["full_text"]:
            print(f"  WARNING: empty full_text for {doc_id} — skipping.")
            continue

        out_path = os.path.join(OUTPUT_DIR, f"case_{doc_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(case, f, ensure_ascii=False, indent=2)
        print(f"  Saved -> {out_path}")
        time.sleep(1)

    print(f"\nDone. Review files in {OUTPUT_DIR}, then run:\n"
          f"  python ingest.py --input ../data/scraped_judgments/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["search", "fetch"], required=True)
    parser.add_argument("--query", default='"Section 138" "Negotiable Instruments Act" dishonour cheque')
    parser.add_argument("--court", default=None)
    parser.add_argument("--max_results", type=int, default=40)
    parser.add_argument("--ids", default=None)
    parser.add_argument("--ids_file", default=None, help="File with case IDs or search result lines")
    parser.add_argument("--category", default=None, help="Category name (e.g. notice_service) to save search results")
    args = parser.parse_args()

    if args.step == "search":
        do_search(args.query, args.court, args.max_results, args.category)
    else:
        ids = []
        if args.ids:
            ids.extend(args.ids.split(","))
        if args.ids_file:
            with open(args.ids_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract the first token (the ID) even if the user pasted the whole search result line
                        doc_id = line.split("|")[0].split()[0]
                        ids.append(doc_id)
                        
        if not ids:
            print("ERROR: --ids or --ids_file required for fetch step")
            return
        do_fetch(ids)


if __name__ == "__main__":
    main()