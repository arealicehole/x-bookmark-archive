#!/usr/bin/env python3
"""
Optional Discord forum mirror — one tagged thread per bookmark.

    python3 forum_post.py
    python3 forum_post.py --dry-run
    python3 forum_post.py --limit 3

Requires DISCORD_BOT_TOKEN + DISCORD_FORUM_CHANNEL_ID and tag map
(DISCORD_TAG_IDS JSON or config.yaml discord.tag_ids).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from config import ARCHIVE, POSTED_FILE, ensure_dirs, load_config


def bot_token() -> str:
    t = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not t:
        raise RuntimeError("DISCORD_BOT_TOKEN not set")
    return t


def discord(method: str, path: str, token: str, payload: dict | None = None):
    url = f"https://discord.com/api/v10{path}"
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (x-bookmark-archive, 1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            code = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        code = e.code
    try:
        return code, json.loads(body) if body else {}
    except json.JSONDecodeError:
        return code, {"_raw": body[:300]}


def post_title(rec: dict) -> str:
    snippet = re.sub(r"\s+", " ", rec.get("text", "")).strip()
    snippet = re.sub(r"https?://t\.co/\S+\s*$", "", snippet).strip()
    who = f"@{rec['author']}" if rec.get("author") else "bookmark"
    title = f"{who}: {snippet}" if snippet else who
    return title[:97] + "..." if len(title) > 100 else title


def post_body(rec: dict) -> str:
    m = rec.get("metrics") or {}
    stats = "  ".join(
        x
        for x in [
            f"❤️ {m['like_count']}" if m.get("like_count") is not None else "",
            f"🔁 {m['retweet_count']}" if m.get("retweet_count") is not None else "",
            f"💬 {m['reply_count']}" if m.get("reply_count") is not None else "",
        ]
        if x
    )
    lines = []
    head = f"**@{rec['author']}**" if rec.get("author") else "**(unknown author)**"
    if rec.get("author_name"):
        head += f" ({rec['author_name']})"
    if rec.get("created_at"):
        head += f" — {rec['created_at'][:10]}"
    lines += [head, "", rec.get("text", "").strip(), "", f"🔗 {rec.get('tweet_url', '')}"]
    ext = [
        u
        for u in rec.get("urls", [])
        if "x.com" not in u and "twitter.com" not in u
    ]
    for u in ext[:3]:
        lines.append(f"↗️ {u}")
    if stats:
        lines.append(stats)
    for med in rec.get("media", []):
        lines.append(med.get("url", ""))
    body = "\n".join(lines)
    return body[:1990] + "…" if len(body) > 2000 else body


def load_posted() -> dict:
    if POSTED_FILE.exists():
        return json.loads(POSTED_FILE.read_text())
    return {}


def main() -> None:
    dry = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    cfg = load_config()
    ensure_dirs()
    dcfg = cfg.get("discord") or {}
    if not dcfg.get("enabled") and not os.environ.get("DISCORD_FORUM_CHANNEL_ID"):
        print("Discord mirror disabled (set discord.enabled or DISCORD_FORUM_CHANNEL_ID).")
        return

    forum_id = dcfg.get("forum_channel_id") or os.environ.get("DISCORD_FORUM_CHANNEL_ID")
    tags = dcfg.get("tag_ids") or {}
    if not isinstance(tags, dict):
        tags = {}
    if not forum_id:
        raise SystemExit("DISCORD_FORUM_CHANNEL_ID / discord.forum_channel_id required")
    if "other" not in tags and tags:
        # allow missing other only if empty tags (no applied_tags)
        pass

    if not ARCHIVE.exists():
        print("no archive yet — run sweep.py first")
        return

    records = [json.loads(l) for l in ARCHIVE.read_text().splitlines() if l.strip()]
    posted = load_posted()
    todo = [r for r in records if r.get("id") and r["id"] not in posted]
    todo.sort(key=lambda r: r.get("created_at", ""))
    if limit is not None:
        todo = todo[:limit]

    if not todo:
        print("0 unposted bookmarks.")
        return

    if dry:
        print(f"DRY RUN — {len(todo)} post(s) would be created:")
        for r in todo[:10]:
            print(f"  [{r.get('category')}] {post_title(r)[:80]}")
        if len(todo) > 10:
            print(f"  … and {len(todo) - 10} more")
        return

    token = bot_token()
    throttle = float(dcfg.get("throttle_seconds") or 2.0)
    made = 0
    for rec in todo:
        applied = []
        cat = rec.get("category") or "other"
        tag = tags.get(cat) or tags.get("other")
        if tag:
            applied = [str(tag)]
        payload = {
            "name": post_title(rec),
            "message": {"content": post_body(rec)},
        }
        if applied:
            payload["applied_tags"] = applied

        for _attempt in range(4):
            code, resp = discord("POST", f"/channels/{forum_id}/threads", token, payload)
            if code in (200, 201):
                posted[rec["id"]] = resp.get("id")
                made += 1
                break
            if code == 429:
                wait = float(resp.get("retry_after", 5)) + 1
                print(f"rate limited, waiting {wait:.0f}s…")
                time.sleep(wait)
                continue
            print(f"FAILED {rec['id']}: HTTP {code} {json.dumps(resp)[:200]}")
            break
        else:
            print(f"FAILED {rec['id']}: rate limit retries exhausted")

        POSTED_FILE.write_text(json.dumps(posted, indent=0))
        time.sleep(throttle)

    print(f"Posted {made}/{len(todo)} bookmark(s) to Discord forum.")


if __name__ == "__main__":
    main()
