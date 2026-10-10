"""Lookup of Sri Lankan endemic birds, keyed by scientific name.

We match on the scientific name (not the common name) because common names
differ between taxonomies, while BirdNET's scientific names are stable.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).with_name("endemics.json")


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    with DATA_FILE.open(encoding="utf-8") as fh:
        birds = json.load(fh)
    return {b["scientific_name"].strip().lower(): b for b in birds}


def lookup(scientific_name: str | None) -> dict | None:
    """Return the endemic entry for a scientific name, or None."""
    return _index().get((scientific_name or "").strip().lower())


def all_endemics() -> list[dict]:
    return list(_index().values())
