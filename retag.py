#!/usr/bin/env python3
"""
Reclassify the local archive with the current classifier.
Optionally sync Discord forum thread tags when posted.json + tag_ids exist.

    python3 retag.py --dry-run
    python3 retag.py
"""

from __future__ import annotations

import json
import sys
import time

from classify import classify
from config import ARCHIVE, POSTED_FILE, load_config
from forum_post import bot_token, discord


def main() -> None:
    dry = "--dry-run" in sys.argv
    cfg = load_config()
    if not ARCHIVE.exists():
        print("no archive")
        sys.exit(1)

    use_llm = bool((cfg.get("classify") or {}).get("use_llm"))
    llm_url = (cfg.get("classify") or {}).get("llm_base_url")
    records = [json.loads(l) for l in ARCHIVE.read_text().splitlines() if l.strip()]
    posted = json.loads(POSTED_FILE.read_text()) if POSTED_FILE.exists() else {}
    tags = (cfg.get("discord") or {}).get("tag_ids") or {}

    changed = []
    for rec in records:
        new_cat = classify(rec, use_llm=use_llm, llm_base_url=llm_url)
        if new_cat != rec.get("category"):
            changed.append((rec, new_cat))

    print(f"{len(records)} records, {len(changed)} category change(s):")
    for rec, new_cat in changed:
        print(
            f"  {rec.get('category')} -> {new_cat}  @{rec.get('author', '')}: "
            f"{rec['text'][:70].replace(chr(10), ' ')}"
        )
    if dry or not changed:
        return

    for rec, new_cat in changed:
        rec["category"] = new_cat

    patched = 0
    if tags and posted:
        token = bot_token()
        for rec, new_cat in changed:
            thread_id = posted.get(rec["id"])
            if not thread_id:
                continue
            tag = tags.get(new_cat) or tags.get("other")
            if not tag:
                continue
            for _ in range(4):
                code, resp = discord(
                    "PATCH",
                    f"/channels/{thread_id}",
                    token,
                    {"applied_tags": [str(tag)]},
                )
                if code in (200, 201):
                    patched += 1
                    break
                if code == 429:
                    time.sleep(float(resp.get("retry_after", 5)) + 1)
                    continue
                print(f"  tag PATCH failed {rec['id']}: HTTP {code}")
                break
            time.sleep(1.5)

    ARCHIVE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    print(f"Archive updated; {patched}/{len(changed)} forum thread tag(s) synced.")


if __name__ == "__main__":
    main()
