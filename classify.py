#!/usr/bin/env python3
"""Classify bookmark text into taxonomy labels. Regex first; optional LLM."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

LABELS = [
    "politics",
    "ai-llm",
    "infra-devops",
    "transcription-audio",
    "media-video",
    "media-image",
    "print-business",
    "crypto",
    "hardware",
    "other",
]

# First match wins. Media before ai-llm so gen-video posts don't all become "ai-llm".
CATEGORIES = [
    (
        "media-video",
        r"\b(ffmpeg|remotion|video editing|video gen\w*|text-to-video|"
        r"image-to-video|\bi2v\b|\bt2v\b|animate|seedance|kling|\bveo\b|"
        r"\bsora\b|hailuo|higgsfield|minimax[- ]?h3|hunyuan ?video|"
        r"wan-?animate|wan2|ltx-?video|ltxv|video model|comfyui)\b",
    ),
    (
        "media-image",
        r"\b(image gen\w*|text-to-image|image-to-image|image-to-3d|"
        r"stable diffusion|seedream|\bflux\b|midjourney|sdxl|z-image|"
        r"qwen-?image|image model|upscal\w*|esrgan|illustrator|sprite|"
        r"\bocr\b)\b",
    ),
    (
        "ai-llm",
        r"\b(llm|gpt|claude|gemini|llama|qwen|mistral|gguf|vllm|lora|qlora|"
        r"fine-?tun\w*|inference|quantiz\w*|transformer|agent|rag|embedding|"
        r"tokenizer|openai|anthropic|huggingface|ollama|mlx|moe|benchmark|"
        r"prompt|sglang|unsloth|text encoder|kv cache|speculative decoding)\b",
    ),
    (
        "infra-devops",
        r"\b(docker|kubernetes|k8s|podman|systemd|linux|fedora|nvidia|cuda|"
        r"self-?host|server|vps|ci/cd|github actions|terraform|ansible|"
        r"monitoring|grafana|prometheus|nginx|cloudflare|tailscale)\b",
    ),
    (
        "transcription-audio",
        r"\b(whisper|transcri\w*|diariz\w*|vad|speech|audio|tts|stt|"
        r"podcast|voice clon\w*|voice gen|\basr\b|suno|ace-step|"
        r"music gen\w*|audio gen\w*)\b",
    ),
    (
        "crypto",
        r"\b(bitcoin|btc|ethereum|\beth\b|crypto|defi|wallet|on-?chain|akash|solana|"
        r"stablecoin|hodl|satoshi)\b",
    ),
    (
        "hardware",
        r"\b(gpu|rtx|radeon|psu|motherboard|nvme|ram|cooling|build|workstation)\b",
    ),
    (
        "print-business",
        r"\b(print|dtg|dtf|screen ?print|shopify|stripe|crm|invoice|"
        r"quote|customer|small business|smb|marketing|sales)\b",
    ),
    (
        "politics",
        r"\b(trump|biden|congress|senate|senator|representative|gop|republican|"
        r"democrat|libertarian|election|primary|legislation|amendment|veto|"
        r"impeach|white house|pentagon|nato|ceasefire|geopolitic\w*|"
        r"constitution|supreme court|maga|deep state)\b",
    ),
]

SYSTEM_PROMPT = (
    "You tag saved tweets for a personal archive. Reply with ONLY one label "
    "from this list: " + ", ".join(LABELS) + ".\n"
    "- politics = government, politicians, elections, policy, war, ideology.\n"
    "- ai-llm = AI models, LLMs, agents, local inference.\n"
    "- media-video = AI video generation / film tools.\n"
    "- media-image = AI image generation, upscaling, OCR.\n"
    "- other = genuinely none of the above."
)


def regex_classify(text_and_urls: str) -> str:
    blob = text_and_urls.lower()
    for cat, pat in CATEGORIES:
        if re.search(pat, blob, re.I):
            return cat
    return "other"


def llm_classify(text: str, base_url: str) -> str | None:
    if not base_url:
        return None
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:800]},
        ],
        "temperature": 0,
        "max_tokens": 16,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None
    try:
        out = (data["choices"][0]["message"].get("content") or "").strip().lower()
    except (KeyError, IndexError, TypeError):
        return None
    for lab in LABELS:
        if lab in out:
            return lab
    return None


def llm_available(base_url: str | None) -> bool:
    if not base_url:
        return False
    url = base_url.rstrip("/") + "/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            body = resp.read().decode()
        return '"data"' in body
    except Exception:
        return False


def classify(rec: dict, use_llm: bool = False, llm_base_url: str | None = None) -> str:
    blob = rec.get("text", "") + " " + " ".join(rec.get("urls") or [])
    cat = regex_classify(blob)
    if cat == "other" and use_llm and llm_base_url:
        guess = llm_classify(rec.get("text", ""), llm_base_url)
        if guess:
            cat = guess
    return cat
