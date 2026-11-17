# Agent brief — x-bookmark-archive

You are setting up or extending **this repository**. The full contract is `README.md`.

## What this is

A **local X bookmarks archive** using the **official X API** (`bookmark.read` OAuth scope — official, not custom). Optional Discord forum mirror. Python 3 stdlib only.

## What you do

1. Clone the repo to the path the user chooses (default: `~/src/x-bookmark-archive` or cwd).
2. `cp .env.example .env` and `cp config.example.yaml config.yaml`.
3. Run `python3 -m unittest tests.test_offline -v` — must pass.
4. Help the user obtain `X_ACCESS_TOKEN` (or token file) with scopes including `bookmark.read`. Do **not** ask them to paste secrets into chat if a local `.env` edit works; instruct exact keys.
5. `python3 sweep.py --dry-run` then `python3 sweep.py`.
6. `python3 query.py --stats`.
7. If they want Discord: wire bot token, forum channel id, tag id JSON; dry-run then limited post.
8. Install cron via `scripts/run-sweep.sh`.
9. Confirm acceptance tests in README.

## Hard rules

- No HTML scraping of x.com.
- No committing secrets or real bookmark archives.
- On `SWEEP BLOCKED` / HTTP 402: report billing/credits; do not fake success.
- Do not hard-code the original author’s personal paths, bot names, or Discord IDs.
- Prefer editing `.env` / `config.yaml` over changing source for site-specific IDs.

## Copy-paste kickoff

```
Clone https://github.com/arealicehole/x-bookmark-archive
Follow README "For agents" end-to-end.
Run offline unit tests first.
Configure .env with X_ACCESS_TOKEN (bookmark.read).
First successful sweep + query --stats is the definition of done.
Discord optional.
```
