"""Field-guide notes.

A small local LLM (served by Ollama) turns *verified facts from our own data
file* into a short note. The model is never asked to recall facts from memory,
because small models make things up. If Ollama isn't running, we return a
static note built from the same facts, so the app never depends on the LLM.
"""
from __future__ import annotations

import json
import os
import urllib.request

ZONE_TEXT = {
    "wet": "the wet zone (south-west lowlands and hills)",
    "montane": "the montane hill country",
    "dry": "the dry zone",
    "island-wide": "forests across much of the island",
}

_cache: dict[tuple[str, str, str], str] = {}


def _base() -> str:
    return os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


def model_name() -> str:
    return os.environ.get("WIHANGA_MODEL", "gemma3:1b")


def llm_available(timeout: float = 0.4) -> bool:
    try:
        with urllib.request.urlopen(_base() + "/api/tags", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ollama_generate(prompt: str, timeout: float = 30.0) -> str:
    body = json.dumps(
        {
            "model": model_name(),
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 90},
        }
    ).encode()
    req = urllib.request.Request(
        _base() + "/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp).get("response", "").strip()


def _zone(entry: dict) -> str:
    return ZONE_TEXT.get(entry.get("zone", ""), "Sri Lanka")


def build_prompt(entry: dict, lang: str = "en") -> str:
    lines = [
        "You are a friendly field guide speaking to a birdwatcher on a trail in Sri Lanka.",
        "Using ONLY the facts below, write at most two short sentences about this bird.",
        "Do not invent facts, sounds, or locations.",
        "Facts:",
        f"- Name: {entry['common_name']}",
        f"- Scientific name: {entry['scientific_name']}",
        "- Endemic to Sri Lanka: yes",
        f"- Mostly found in: {_zone(entry)}",
    ]
    if entry.get("notes"):
        lines.append(f"- Note: {entry['notes']}")
    if lang == "si":
        lines.append("Write the answer in Sinhala.")
    return "\n".join(lines)


def static_note(entry: dict | None, common_name: str, scientific_name: str) -> str:
    if entry is None:
        return f"{common_name} ({scientific_name}). Not in this app's endemic list."
    text = f"{entry['common_name']} is endemic to Sri Lanka, mostly found in {_zone(entry)}."
    if entry.get("notes"):
        text += " " + entry["notes"]
    return text


def field_note(entry: dict | None, common_name: str, scientific_name: str, lang: str = "en") -> dict:
    """Return {"text": ..., "source": "llm" | "static"}."""
    fallback = {"text": static_note(entry, common_name, scientific_name), "source": "static"}
    if entry is None:
        return fallback  # nothing verified to ground a model on, so don't ask one

    key = (scientific_name.lower(), lang, model_name())
    if key in _cache:
        return {"text": _cache[key], "source": "llm"}
    try:
        text = _ollama_generate(build_prompt(entry, lang))
    except Exception:
        return fallback
    if not text:
        return fallback
    _cache[key] = text
    return {"text": text, "source": "llm"}
