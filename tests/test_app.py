import io
import wave

import pytest

from wihanga import endemics, guide
from wihanga.app import create_app
from wihanga.identify import Detection, DemoIdentifier


def make_wav(seconds: int = 1, rate: int = 48000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * rate * seconds)
    return buf.getvalue()


class SameBird:
    name = "same"

    def identify(self, wav_path, lat=None, lon=None, when=None):
        return [Detection("Sri Lanka Junglefowl", "Gallus lafayettii", 0.9)]


@pytest.fixture(autouse=True)
def llm_is_down(monkeypatch):
    # Port 9 (discard): nothing listens, so Ollama looks switched off.
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")
    guide._cache.clear()


@pytest.fixture
def make_client(tmp_path):
    def _make(identifier):
        return create_app(identifier=identifier, db_path=str(tmp_path / "s.db")).test_client()

    return _make


@pytest.fixture
def client(make_client):
    return make_client(DemoIdentifier())


def post_audio(client, payload=None):
    data = {"audio": (io.BytesIO(payload if payload is not None else make_wav()), "chunk.wav")}
    return client.post("/api/identify", data=data, content_type="multipart/form-data")


# ---------- API ----------

def test_health(client):
    j = client.get("/api/health").get_json()
    assert j["identifier"] == "Demo (fake)"
    assert j["llm"] is False
    assert j["endemics"] >= 20


def test_identify_flags_endemics(client):
    dets = post_audio(client).get_json()["detections"]
    assert dets[0]["scientific_name"] == "Gallus lafayettii"
    assert dets[0]["endemic"] is True
    assert dets[1]["scientific_name"] == "Acridotheres tristis"
    assert dets[1]["endemic"] is False


def test_identify_requires_audio(client):
    r = client.post("/api/identify", data={}, content_type="multipart/form-data")
    assert r.status_code == 400


def test_identify_rejects_non_wav(client):
    assert post_audio(client, b"definitely not a wav file").status_code == 415


def test_missing_birdnet_gives_503(make_client):
    class NoBirdNET:
        name = "x"

        def identify(self, *a, **k):
            raise ImportError("birdnetlib")

    assert post_audio(make_client(NoBirdNET())).status_code == 503


def test_same_bird_is_logged_once(make_client):
    client = make_client(SameBird())
    first = post_audio(client).get_json()["detections"][0]
    second = post_audio(client).get_json()["detections"][0]
    assert first["new_in_log"] is True
    assert second["new_in_log"] is False
    assert len(client.get("/api/sightings").get_json()["sightings"]) == 1


def test_csv_export(make_client):
    client = make_client(SameBird())
    post_audio(client)
    r = client.get("/api/sightings.csv")
    assert r.mimetype == "text/csv"
    text = r.get_data(as_text=True)
    assert text.startswith("ts,common_name,scientific_name")
    assert "Gallus lafayettii" in text


def test_ui_is_served(client):
    assert b"Wihanga Nada" in client.get("/").data
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


# ---------- field notes ----------

def test_note_falls_back_to_static_when_llm_is_down(client):
    j = client.get("/api/note?sci=Gallus lafayettii&name=Sri Lanka Junglefowl").get_json()
    assert j["source"] == "static"
    assert "endemic" in j["text"]


def test_note_never_asks_llm_about_unverified_birds(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("LLM must not be called without verified facts")

    monkeypatch.setattr(guide, "_ollama_generate", boom)
    j = client.get("/api/note?sci=Acridotheres tristis&name=Common Myna").get_json()
    assert j["source"] == "static"
    assert "endemic list" in j["text"]


def test_note_prompt_is_grounded_and_cached(client, monkeypatch):
    prompts = []

    def fake(prompt, timeout=30.0):
        prompts.append(prompt)
        return "A lovely bird."

    monkeypatch.setattr(guide, "_ollama_generate", fake)
    url = "/api/note?sci=Gallus lafayettii&name=Sri Lanka Junglefowl"
    first = client.get(url).get_json()
    second = client.get(url).get_json()
    assert first == {"text": "A lovely bird.", "source": "llm"}
    assert second["source"] == "llm"
    assert len(prompts) == 1  # second call came from the cache
    assert "Gallus lafayettii" in prompts[0]
    assert "ONLY" in prompts[0] and "Do not invent" in prompts[0]


def test_sinhala_option_reaches_prompt(client, monkeypatch):
    prompts = []
    monkeypatch.setattr(guide, "_ollama_generate", lambda p, timeout=30.0: prompts.append(p) or "ok")
    client.get("/api/note?sci=Urocissa ornata&name=Blue-Magpie&lang=si")
    assert "Sinhala" in prompts[0]


# ---------- data ----------

def test_endemics_data_is_consistent():
    birds = endemics.all_endemics()
    raw = endemics.DATA_FILE.read_text(encoding="utf-8")
    assert raw.count('"scientific_name"') == len(birds), "duplicate scientific names"
    for b in birds:
        assert b["zone"] in guide.ZONE_TEXT, b
        assert isinstance(b["in_birdnet"], bool), b
        assert "name_si" in b, b
        assert b["common_name"] and b["notes"], b
    assert sum(b["in_birdnet"] for b in birds) >= 10


def test_lookup_is_case_insensitive():
    assert endemics.lookup("  gallus LAFAYETTII ")["common_name"] == "Sri Lanka Junglefowl"
    assert endemics.lookup("Passer domesticus") is None
    assert endemics.lookup(None) is None
