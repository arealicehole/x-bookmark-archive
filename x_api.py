#!/usr/bin/env python3
"""X API v2 helpers — OAuth2 user token + bookmarks fetch. Stdlib only."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.x.com"
USER_AGENT = "x-bookmark-archive/1.0"
API_PARAMS = (
    "max_results=100"
    "&expansions=author_id,attachments.media_keys"
    "&tweet.fields=created_at,public_metrics,entities,attachments"
    "&user.fields=username,name"
    "&media.fields=url,preview_image_url,type,width,height,variants"
)


def _token_from_file(path: Path) -> dict:
    return json.loads(path.read_text())


def get_access_token() -> str:
    """Resolve a user OAuth2 access token.

    Order:
      1. X_ACCESS_TOKEN env
      2. X_OAUTH_TOKEN_FILE JSON (access_token; optional refresh via x-cli)
      3. ./oauth2_tokens.json next to the project
    """
    direct = os.environ.get("X_ACCESS_TOKEN", "").strip()
    if direct:
        return direct

    candidates = []
    if os.environ.get("X_OAUTH_TOKEN_FILE"):
        candidates.append(Path(os.environ["X_OAUTH_TOKEN_FILE"]).expanduser())
    candidates.append(Path(__file__).resolve().parent / "oauth2_tokens.json")

    tok_path = next((p for p in candidates if p.exists()), None)
    if not tok_path:
        raise RuntimeError(
            "No X access token. Set X_ACCESS_TOKEN or X_OAUTH_TOKEN_FILE "
            "(OAuth2 user token with bookmark.read). See README."
        )

    tok = _token_from_file(tok_path)
    expires = float(tok.get("expires_at") or 0)
    if expires and expires < time.time() + 300:
        _try_refresh_via_xcli()
        tok = _token_from_file(tok_path)

    access = tok.get("access_token")
    if not access:
        raise RuntimeError(f"No access_token in {tok_path}")
    return access


def _try_refresh_via_xcli() -> None:
    """Optional: if x-cli is installed and logged in, poke it to refresh tokens."""
    xcli = os.environ.get("X_CLI_PATH", "x-cli")
    try:
        subprocess.run(
            [xcli, "-j", "me", "bookmarks", "--max", "1"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass


def api_get(path: str, token: str) -> dict:
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        status = e.code
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            raise RuntimeError(f"X API HTTP {status}: {body[:300]}") from e
        # Surface billing / auth clearly
        detail = json.dumps(data)[:400]
        if status == 402:
            raise RuntimeError(
                f"X API 402 (credits/billing depleted on the developer app): {detail}"
            ) from e
        if status in (401, 403):
            raise RuntimeError(
                f"X API {status} (auth/scopes — re-auth with bookmark.read): {detail}"
            ) from e
        raise RuntimeError(f"X API HTTP {status}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"X API network error: {e}") from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"X API non-JSON ({status}): {body[:300]}") from e

    if "errors" in data and "data" not in data:
        raise RuntimeError(f"X API error: {json.dumps(data['errors'])[:300]}")
    if data.get("status") in (401, 403) or (
        "detail" in data and "data" not in data and "title" in data
    ):
        raise RuntimeError(f"X API problem: {json.dumps(data)[:300]}")
    return data


def media_url(m: dict) -> str | None:
    if m.get("type") == "photo":
        return m.get("url")
    variants = [
        v
        for v in (m.get("variants") or [])
        if v.get("content_type") == "video/mp4"
    ]
    if variants:
        return max(variants, key=lambda v: v.get("bit_rate") or 0).get("url")
    return m.get("preview_image_url")


def normalize(tw: dict, users: dict, media: dict) -> dict:
    author = users.get(tw.get("author_id"), {}) or {}
    handle = author.get("username", "") or ""
    media_out = []
    for key in (tw.get("attachments") or {}).get("media_keys", []) or []:
        m = media.get(key)
        if not m:
            continue
        url = media_url(m)
        if url:
            media_out.append({"type": m.get("type"), "url": url})
    urls = []
    for u in (tw.get("entities") or {}).get("urls", []) or []:
        if isinstance(u, dict) and u.get("expanded_url"):
            urls.append(u["expanded_url"])
    tid = str(tw.get("id", ""))
    return {
        "id": tid,
        "author": handle,
        "author_name": author.get("name", "") or "",
        "text": tw.get("text", "") or "",
        "urls": urls,
        "media": media_out,
        "created_at": tw.get("created_at", "") or "",
        "metrics": tw.get("public_metrics") or {},
        "tweet_url": (
            f"https://x.com/{handle}/status/{tid}"
            if handle
            else f"https://x.com/i/status/{tid}"
        ),
    }


def fetch_bookmarks(max_pages: int = 20) -> list[dict]:
    token = get_access_token()
    me = api_get("/2/users/me", token)
    uid = (me.get("data") or {}).get("id")
    if not uid:
        raise RuntimeError(f"could not resolve user: {json.dumps(me)[:200]}")

    records: list[dict] = []
    page_token = None
    for _ in range(max_pages):
        path = f"/2/users/{uid}/bookmarks?{API_PARAMS}"
        if page_token:
            path += f"&pagination_token={page_token}"
        data = api_get(path, token)
        tweets = data.get("data") or []
        inc = data.get("includes") or {}
        users = {u["id"]: u for u in inc.get("users", [])}
        media = {m["media_key"]: m for m in inc.get("media", [])}
        for tw in tweets:
            records.append(normalize(tw, users, media))
        page_token = (data.get("meta") or {}).get("next_token")
        if not page_token or not tweets:
            break
    return records
