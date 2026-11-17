#!/usr/bin/env python3
"""
Sweep X bookmarks into a local JSONL archive.

Usage:
    python3 sweep.py            # fetch + write
    python3 sweep.py --dry-run  # fetch + classify, no writes
    python3 sweep.py --quiet    # no stdout when 0 new (cron)

Exit codes:
    0  ok
    2  SWEEP BLOCKED (auth, billing, API) — message on stdout
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime

from classify import classify
from config import (
    ARCHIVE,
    DIGEST,
    SEEN_FILE,
    ensure_dirs,
    load_config,
)
from x_api import fetch_bookmarks


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def load_archive() -> list[dict]:
    if not ARCHIVE.exists():
        return []
    out = []
    for line in ARCHIVE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def main() -> None:
    dry = "--dry-run" in sys.argv
    quiet = "--quiet" in sys.argv
    cfg = load_config()
    ensure_dirs()

    try:
        records = fetch_bookmarks(max_pages=int(cfg.get("max_bookmark_pages") or 20))
    except RuntimeError as e:
        print(f"SWEEP BLOCKED: {e}")
        sys.exit(2)

    use_llm = bool((cfg.get("classify") or {}).get("use_llm"))
    llm_url = (cfg.get("classify") or {}).get("llm_base_url")

    for rec in records:
        rec["category"] = classify(rec, use_llm=use_llm, llm_base_url=llm_url)

    seen = load_seen()
    new_recs = [r for r in records if r.get("id") and r["id"] not in seen]

    today = datetime.now().strftime("%Y-%m-%d")
    stamp = datetime.now().strftime("%H:%M")

    if not dry:
        fresh = {r["id"]: r for r in records if r.get("id")}
        archive = load_archive()
        changed = False
        for row in archive:
            f = fresh.get(row.get("id"))
            if f and (not row.get("author") or (f.get("media") and not row.get("media"))):
                row.update(
                    {
                        k: f[k]
                        for k in ("author", "author_name", "media", "urls", "metrics")
                        if k in f
                    }
                )
                # keep newer category if still "other"
                if row.get("category") == "other" and f.get("category"):
                    row["category"] = f["category"]
                changed = True
        if new_recs:
            for rec in new_recs:
                rec["swept_at"] = f"{today} {stamp}"
                archive.append(rec)
            seen.update(r["id"] for r in new_recs)
            SEEN_FILE.write_text(json.dumps(sorted(seen), indent=0))
        if changed or new_recs:
            ARCHIVE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in archive))

        if new_recs:
            by_cat: dict[str, list] = {}
            for rec in new_recs:
                by_cat.setdefault(rec["category"], []).append(rec)
            digest_path = DIGEST / f"{today}.md"
            with digest_path.open("a", encoding="utf-8") as f:
                f.write(f"\n## Sweep {stamp} — {len(new_recs)} new bookmark(s)\n")
                for cat in sorted(by_cat):
                    f.write(f"\n### {cat} ({len(by_cat[cat])})\n")
                    for rec in by_cat[cat]:
                        snippet = re.sub(r"\s+", " ", rec["text"])[:200]
                        f.write(f"- **@{rec['author']}**: {snippet}\n  {rec['tweet_url']}\n")
                        for u in rec.get("urls", [])[:3]:
                            f.write(f"  link: {u}\n")

    if not new_recs:
        if not quiet:
            print(
                f"Sweep OK — {len(records)} bookmarks checked, 0 new"
                + (" (dry run)" if dry else " (archive may be enriched).")
            )
        return

    by_cat = {}
    for rec in new_recs:
        by_cat.setdefault(rec["category"], []).append(rec)
    print(f"NEW BOOKMARKS: {len(new_recs)} (of {len(records)} checked)")
    for cat in sorted(by_cat):
        print(f"\n[{cat}]")
        for rec in by_cat[cat]:
            snippet = re.sub(r"\s+", " ", rec["text"])[:120]
            print(f"  • @{rec['author']}: {snippet}")
            print(f"    {rec['tweet_url']}")
    if dry:
        print("\n(dry run — state not written)")


if __name__ == "__main__":
    main()
