"""Flask app: serves the hands-free UI and a tiny local JSON API."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from . import endemics, guide
from .db import SightingsDB
from .identify import BirdNETIdentifier

STATIC_DIR = Path(__file__).with_name("static")


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def create_app(identifier=None, db_path: str | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # a 6 s mono WAV is ~0.6 MB

    identifier = identifier or BirdNETIdentifier()
    db = SightingsDB(db_path or os.environ.get("WIHANGA_DB", "sightings.db"))

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name):
        return send_from_directory(STATIC_DIR, name)

    @app.get("/api/health")
    def health():
        return jsonify(
            identifier=getattr(identifier, "name", "custom"),
            llm=guide.llm_available(),
            model=guide.model_name(),
            endemics=len(endemics.all_endemics()),
        )

    @app.post("/api/identify")
    def api_identify():
        upload = request.files.get("audio")
        if upload is None:
            return jsonify(error="missing 'audio' file"), 400
        head = upload.stream.read(12)
        upload.stream.seek(0)
        if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
            return jsonify(error="audio must be a WAV file"), 415

        lat, lon = _float(request.form.get("lat")), _float(request.form.get("lon"))
        # BirdNET uses location + week of year to filter impossible species.
        # Without GPS we fall back to the centre of Sri Lanka.
        q_lat, q_lon = (lat, lon) if lat is not None and lon is not None else (7.8731, 80.7718)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            upload.save(tmp)
            path = tmp.name
        try:
            found = identifier.identify(path, q_lat, q_lon, datetime.now())
        except ImportError:
            return (
                jsonify(error="BirdNET is not installed. Run with --demo, or see the README."),
                503,
            )
        except Exception:
            app.logger.exception("identify failed")
            return jsonify(error="identification failed"), 500
        finally:
            os.unlink(path)

        out = []
        for d in found:
            entry = endemics.lookup(d.scientific_name)
            logged = db.log(d.common_name, d.scientific_name, d.confidence, bool(entry), lat, lon)
            out.append(
                {
                    "common_name": d.common_name,
                    "scientific_name": d.scientific_name,
                    "confidence": round(d.confidence, 3),
                    "endemic": entry is not None,
                    "zone": entry.get("zone") if entry else None,
                    "new_in_log": logged,
                }
            )
        return jsonify(detections=out)

    @app.get("/api/note")
    def api_note():
        sci = request.args.get("sci", "").strip()
        if not sci:
            return jsonify(error="missing 'sci'"), 400
        name = request.args.get("name", "").strip() or sci
        lang = "si" if request.args.get("lang") == "si" else "en"
        return jsonify(guide.field_note(endemics.lookup(sci), name, sci, lang))

    @app.get("/api/sightings")
    def api_sightings():
        return jsonify(sightings=db.recent())

    @app.get("/api/sightings.csv")
    def api_sightings_csv():
        return Response(
            db.to_csv(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=wihanga-sightings.csv"},
        )

    return app
