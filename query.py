#!/usr/bin/env python3
"""
Query the local bookmark archive (no X API calls).

    python3 query.py massie
    python3 query.py --cat politics
    python3 query.py --cat ai-llm llama
    python3 query.py --stats
"""

from __future__ import annotations

import json
import sys

from config import ARCHIVE, load_dotenv


def main() -> None:
    load_dotenv()
    args = sys.argv[1:]
    if not ARCHIVE.exists():
        print("No archive yet — run sweep.py first.")
        sys.exit(1)

    records = [json.loads(l) for l in ARCHIVE.read_text().splitlines() if l.strip()]

    if "--stats" in args:
        counts: dict[str, int] = {}
        for r in records:
            c = r.get("category", "?")
            counts[c] = counts.get(c, 0) + 1
        for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"{cat:22} {n}")
        print(f"{'TOTAL':22} {len(records)}")
        return

    cat = None
    if "--cat" in args:
        i = args.index("--cat")
        cat = args[i + 1]
        args = args[:i] + args[i + 2 :]
    terms = [a.lower() for a in args]

    hits = []
    for r in records:
        if cat and r.get("category") != cat:
            continue
        blob = (r.get("text", "") + " " + r.get("author", "")).lower()
        if terms and not all(t in blob for t in terms):
            continue
        if not terms and not cat:
            continue
        hits.append(r)

    # --cat alone lists that category
    if cat and not terms:
        hits = [r for r in records if r.get("category") == cat]

    for r in hits:
        print(f"[{r.get('category')}] @{r.get('author', '?')} — {str(r.get('created_at', ''))[:10]}")
        print(f"  {r.get('text', '')[:180].replace(chr(10), ' ')}")
        print(f"  {r.get('tweet_url', '')}")
    print(f"\n{len(hits)} hit(s) of {len(records)} bookmarks.")


if __name__ == "__main__":
    main()
