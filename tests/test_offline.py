#!/usr/bin/env python3
"""Offline unit checks — no network, no tokens required."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from classify import classify, regex_classify  # noqa: E402
from x_api import normalize  # noqa: E402


class TestClassify(unittest.TestCase):
    def test_ai(self):
        self.assertEqual(regex_classify("new llama GGUF on huggingface"), "ai-llm")

    def test_video_before_ai(self):
        self.assertEqual(regex_classify("kling text-to-video model release"), "media-video")

    def test_other(self):
        self.assertEqual(regex_classify("nice weather today"), "other")

    def test_classify_record(self):
        rec = {"text": "docker on fedora with systemd", "urls": []}
        self.assertEqual(classify(rec, use_llm=False), "infra-devops")


class TestNormalize(unittest.TestCase):
    def test_basic(self):
        tw = {
            "id": "99",
            "text": "hello",
            "author_id": "u1",
            "created_at": "2026-01-01T00:00:00.000Z",
            "public_metrics": {"like_count": 3},
            "entities": {"urls": [{"expanded_url": "https://example.com"}]},
            "attachments": {"media_keys": ["m1"]},
        }
        users = {"u1": {"username": "bob", "name": "Bob"}}
        media = {"m1": {"type": "photo", "url": "https://pbs.twimg.com/x.jpg"}}
        rec = normalize(tw, users, media)
        self.assertEqual(rec["id"], "99")
        self.assertEqual(rec["author"], "bob")
        self.assertEqual(rec["urls"], ["https://example.com"])
        self.assertEqual(rec["media"][0]["url"], "https://pbs.twimg.com/x.jpg")
        self.assertIn("bob/status/99", rec["tweet_url"])


class TestSweepIdempotentLogic(unittest.TestCase):
    def test_dedupe(self):
        seen = {"1", "2"}
        records = [{"id": "2"}, {"id": "3"}]
        new = [r for r in records if r["id"] not in seen]
        self.assertEqual([r["id"] for r in new], ["3"])


class TestQueryFixture(unittest.TestCase):
    def test_jsonl_roundtrip(self):
        line = {
            "id": "1",
            "author": "x",
            "text": "llama rocks",
            "category": "ai-llm",
            "tweet_url": "https://x.com/x/status/1",
            "urls": [],
            "media": [],
            "created_at": "2026-01-01T00:00:00.000Z",
            "metrics": {},
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bookmarks.jsonl"
            p.write_text(json.dumps(line) + "\n")
            rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
            self.assertEqual(rows[0]["category"], "ai-llm")


if __name__ == "__main__":
    unittest.main()
