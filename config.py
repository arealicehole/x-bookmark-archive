#!/usr/bin/env python3
"""Load .env + optional config.yaml. Stdlib only."""

from __future__ import annotations

import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENV_FILE = BASE / ".env"
CONFIG_FILE = BASE / "config.yaml"
STATE = BASE / "state"
DIGEST = BASE / "digest"
ARCHIVE = STATE / "bookmarks.jsonl"
SEEN_FILE = STATE / "seen_ids.json"
POSTED_FILE = STATE / "posted.json"

DEFAULTS = {
    "max_bookmark_pages": 20,
    "quiet_when_empty": True,
    "classify": {"use_llm": False, "llm_base_url": None},
    "discord": {"enabled": False, "throttle_seconds": 2.0, "forum_channel_id": None, "tag_ids": {}},
}


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _parse_simple_yaml(text: str) -> dict:
    """Tiny subset parser: top-level keys, one-level nested dicts, scalars.
    Good enough for config.example.yaml — no dependency on PyYAML.
    """
    root: dict = {}
    stack: list[tuple[int, dict]] = [(0, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
        cur = stack[-1][1]
        if rest == "" or rest is None:
            child: dict = {}
            cur[key] = child
            stack.append((indent + 2, child))
            continue
        if rest.startswith("#"):
            child = {}
            cur[key] = child
            stack.append((indent + 2, child))
            continue
        # strip inline comment
        if " #" in rest:
            rest = rest.split(" #", 1)[0].strip()
        if rest.lower() in ("true", "yes"):
            val: object = True
        elif rest.lower() in ("false", "no"):
            val = False
        elif rest.lower() in ("null", "none", "~"):
            val = None
        else:
            try:
                if "." in rest:
                    val = float(rest)
                else:
                    val = int(rest)
            except ValueError:
                val = rest.strip('"').strip("'")
        cur[key] = val
    return root


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    load_dotenv()
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if CONFIG_FILE.exists():
        try:
            parsed = _parse_simple_yaml(CONFIG_FILE.read_text())
            cfg = deep_merge(cfg, parsed)
        except Exception as e:
            raise RuntimeError(f"failed to parse {CONFIG_FILE}: {e}") from e

    # Env overrides
    if os.environ.get("CLASSIFY_USE_LLM", "").lower() in ("1", "true", "yes"):
        cfg["classify"]["use_llm"] = True
    if os.environ.get("CLASSIFY_LLM_URL"):
        cfg["classify"]["llm_base_url"] = os.environ["CLASSIFY_LLM_URL"].rstrip("/")
    if os.environ.get("DISCORD_FORUM_CHANNEL_ID"):
        cfg["discord"]["forum_channel_id"] = os.environ["DISCORD_FORUM_CHANNEL_ID"]
        cfg["discord"]["enabled"] = True
    if os.environ.get("DISCORD_TAG_IDS"):
        cfg["discord"]["tag_ids"] = json.loads(os.environ["DISCORD_TAG_IDS"])
    if os.environ.get("DISCORD_ENABLED", "").lower() in ("1", "true", "yes"):
        cfg["discord"]["enabled"] = True
    return cfg


def ensure_dirs() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    DIGEST.mkdir(parents=True, exist_ok=True)
