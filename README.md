# x-bookmark-archive

**Local archive of your X (Twitter) bookmarks via the official API — optional Discord forum mirror.**

Not a website scraper. A small Python tool that polls X’s Bookmarks API on a schedule, stores enriched records in JSONL on disk, classifies them, and can mirror each new one into a Discord forum thread.

**Stdlib only** (Python 3.10+). No pip packages required.

---

## One-liner

> Bookmark on X → cron + OAuth bookmarks API (paginated) → local JSONL + tags → optional Discord forum; search offline forever.

---

## For humans (30 seconds)

1. You star posts on X like normal.
2. This tool uses an **official X OAuth scope** called **`bookmark.read`** (we did not invent it).
3. On a timer it downloads your bookmarks (with author, media, links), skips ones it already saved, and appends the rest to `state/bookmarks.jsonl`.
4. You search that file later with `query.py` — no API cost to re-find something.
5. Optional: post each new bookmark into a Discord **forum** channel with category tags.

You need: an X developer app, a user OAuth2 token with the right scopes, and **API credits that aren’t empty** (402 = billing, not “broken script”).

---

## For agents — implement / install locally

```text
GOAL: Clone this repo, configure secrets, run offline tests, auth once, first sweep, optional Discord, cron.

DO NOT: scrape x.com HTML; commit .env or real bookmarks; hard-code personal paths or Discord snowflakes into source.
```

### 1. Clone

```bash
git clone https://github.com/arealicehole/x-bookmark-archive.git
cd x-bookmark-archive
cp .env.example .env
cp config.example.yaml config.yaml
chmod +x scripts/run-sweep.sh
```

### 2. Offline tests (no network)

```bash
python3 -m unittest tests.test_offline -v
```

All must pass before touching production credentials.

### 3. X developer setup (human in the loop for browser login)

1. Create an X developer project/app with **OAuth 2.0**.
2. Request scopes including at least:
   - `bookmark.read` — required
   - `tweet.read`, `users.read` — typical companions for expansions
   - `offline.access` — refresh for unattended cron
3. Complete user authorization once.
4. Put a **user** access token into `.env`:

```bash
X_ACCESS_TOKEN=...
```

Or point at a token JSON file:

```bash
X_OAUTH_TOKEN_FILE=/path/to/oauth2_tokens.json
# JSON shape: {"access_token":"...","refresh_token":"...","expires_at": 1730000000}
```

Optional: if [x-cli](https://github.com/arealicehole/x-cli) (or any `x-cli` on PATH) manages refresh, set `X_CLI_PATH` and keep the token file updated; the sweeper will poke x-cli when `expires_at` is near.

**`bookmark.read` is an official X API OAuth 2.0 scope**, not a custom invention of this project.

### 4. First sweep

```bash
python3 sweep.py --dry-run   # fetch + classify, no writes
python3 sweep.py             # write state/
python3 query.py --stats
python3 query.py llama
```

Exit code **2** + `SWEEP BLOCKED: …` means auth, scopes, or **billing/credits (402)**. Do not invent workarounds; fix the developer app / re-auth.

### 5. Optional Discord forum mirror

1. Create a Discord bot; invite it to a server with permission to create posts in a **Forum** channel.
2. Create forum tags matching your categories (see classify labels).
3. In `.env`:

```bash
DISCORD_BOT_TOKEN=...
DISCORD_FORUM_CHANNEL_ID=...
DISCORD_ENABLED=1
DISCORD_TAG_IDS={"ai-llm":"TAG_ID","infra-devops":"TAG_ID","other":"TAG_ID",...}
```

4. Dry-run then post:

```bash
python3 forum_post.py --dry-run
python3 forum_post.py --limit 3
```

Checkpoint file: `state/posted.json` (tweet id → thread id). Safe to re-run.

### 6. Cron

```cron
0 */2 * * * /path/to/x-bookmark-archive/scripts/run-sweep.sh >>/path/to/logs/x-bookmark-sweep.log 2>&1
```

The wrapper **always prints errors** on failure (never discard `SWEEP BLOCKED`).

### 7. Acceptance checklist

| # | Check |
|---|--------|
| T1 | Missing token → exit 2, clear message |
| T2 | First sweep creates `state/bookmarks.jsonl` + `seen_ids.json` |
| T3 | Second sweep → 0 new, no dupes |
| T4 | `query.py --stats` works |
| T5 | `query.py <term>` finds a known bookmark |
| T6 | `--dry-run` does not grow the archive |
| T7 | Discord off → forum_post no-ops cleanly |
| T8 | Discord dry-run lists posts only |

---

## Architecture

```
X API v2  ──OAuth2 user token──►  sweep.py
  GET /2/users/me
  GET /2/users/{id}/bookmarks   (paginated + expansions)
                                    │
                                    ├─ classify.py (regex, optional LLM)
                                    ├─ state/bookmarks.jsonl
                                    ├─ state/seen_ids.json
                                    └─ digest/YYYY-MM-DD.md
                                         │
                                         ▼
                               forum_post.py (optional Discord)
                               state/posted.json
                                         │
                                         ▼
                                    query.py (local only)
```

### API params used

```
max_results=100
expansions=author_id,attachments.media_keys
tweet.fields=created_at,public_metrics,entities,attachments
user.fields=username,name
media.fields=url,preview_image_url,type,width,height,variants
pagination_token=…
```

---

## JSONL record shape

```json
{
  "id": "123",
  "author": "handle",
  "author_name": "Name",
  "text": "…",
  "urls": ["https://…"],
  "media": [{"type": "photo", "url": "https://…"}],
  "created_at": "2026-01-01T00:00:00.000Z",
  "metrics": {"like_count": 1},
  "tweet_url": "https://x.com/handle/status/123",
  "category": "ai-llm",
  "swept_at": "2026-01-02 10:00"
}
```

---

## Commands

| Command | Purpose |
|---------|---------|
| `python3 sweep.py` | Pull bookmarks → archive |
| `python3 sweep.py --dry-run` | No writes |
| `python3 sweep.py --quiet` | Silent when 0 new |
| `python3 query.py --stats` | Category counts |
| `python3 query.py TERM` | Local search |
| `python3 forum_post.py` | Discord mirror |
| `python3 retag.py` | Re-run classifier (+ optional Discord tag sync) |
| `scripts/run-sweep.sh` | Cron entrypoint |

---

## Layout

```text
x-bookmark-archive/
  README.md
  AGENT.md
  LICENSE
  .env.example
  config.example.yaml
  config.py          # dotenv + tiny YAML
  x_api.py           # OAuth token + bookmarks fetch
  classify.py        # regex (+ optional LLM)
  sweep.py
  query.py
  forum_post.py
  retag.py
  scripts/run-sweep.sh
  state/             # gitignored data
  digest/            # gitignored digests
  tests/
```

---

## Security

- Never commit `.env`, token JSON, or real `state/bookmarks.jsonl`.
- Bookmarks are personal data.
- Mask tokens in logs; this code never prints the bearer.

---

## License

MIT. You are responsible for complying with X’s developer terms and Discord’s policies. API access and billing are between you and X.
