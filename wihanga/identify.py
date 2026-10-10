"""Bird-sound identification.

BirdNET runs fully on this machine: the model ships inside the `birdnetlib`
pip package, so after installation no network is needed.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class Detection:
    common_name: str
    scientific_name: str
    confidence: float


class Identifier(Protocol):
    name: str

    def identify(
        self, wav_path: str, lat: float | None, lon: float | None, when: datetime | None
    ) -> list[Detection]: ...


class BirdNETIdentifier:
    name = "BirdNET 2.4"

    def __init__(self, min_conf: float = 0.35):
        self.min_conf = min_conf
        self._analyzer = None
        # The TFLite interpreter is not thread-safe; serialise calls.
        self._lock = threading.Lock()

    def _get_analyzer(self):
        if self._analyzer is None:
            # Heavy import, so do it lazily: the server starts instantly and
            # --demo mode works without TensorFlow installed.
            from birdnetlib.analyzer import Analyzer

            self._analyzer = Analyzer()
        return self._analyzer

    def identify(self, wav_path, lat=None, lon=None, when=None):
        from birdnetlib import Recording

        with self._lock:
            recording = Recording(
                self._get_analyzer(),
                wav_path,
                lat=lat,
                lon=lon,
                date=when or datetime.now(),
                min_conf=self.min_conf,
            )
            recording.analyze()

        best: dict[str, Detection] = {}
        for d in recording.detections:
            sci = d["scientific_name"]
            if sci not in best or d["confidence"] > best[sci].confidence:
                best[sci] = Detection(d["common_name"], sci, float(d["confidence"]))
        return sorted(best.values(), key=lambda x: -x.confidence)


class DemoIdentifier:
    """Canned results that cycle on every call. For trying the UI without
    BirdNET installed, and for tests. It does not listen to the audio."""

    name = "Demo (fake)"

    _SEQUENCE = [
        [
            Detection("Sri Lanka Junglefowl", "Gallus lafayettii", 0.91),
            Detection("Common Myna", "Acridotheres tristis", 0.55),
        ],
        [Detection("Sri Lanka Blue-Magpie", "Urocissa ornata", 0.84)],
        [Detection("Layard's Parakeet", "Psittacula calthrapae", 0.77)],
        [Detection("Red-vented Bulbul", "Pycnonotus cafer", 0.62)],
        [],
    ]

    def __init__(self):
        self._i = 0
        self._lock = threading.Lock()

    def identify(self, wav_path, lat=None, lon=None, when=None):
        with self._lock:
            result = self._SEQUENCE[self._i % len(self._SEQUENCE)]
            self._i += 1
        return list(result)
