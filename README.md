# Wihanga Nada (විහඟ නාද)

An offline bird-call identifier for Sri Lanka. Tap **Listen**, put the phone away, look up. The app says the bird's name out loud, flags Sri Lankan endemics, and keeps a trip log. Everything runs on your own machine, with no internet and no account.

Built for the Hacktoberfest Open-Source AI Challenge, week 1: *Touch Grass*.

## How it works

```
 browser (mic, speech)              your laptop / Raspberry Pi
 ┌──────────────────┐   6 s WAV    ┌──────────────────────────────────────┐
 │ record, resample │ ───────────▶ │ Flask                                │
 │ speak the name   │ ◀─────────── │  ├─ BirdNET 2.4 (TFLite, local)      │
 └──────────────────┘   detections │  ├─ endemics.json (verified facts)   │
                                   │  ├─ Ollama + small LLM (optional)    │
                                   │  └─ SQLite trip log (local file)     │
                                   └──────────────────────────────────────┘
```

* **BirdNET 2.4** does the actual identification. The model ships *inside* the `birdnetlib` pip package, so after `pip install` it needs no network. GPS (or central Sri Lanka as a fallback) plus the week of the year narrow the candidates to the species that can really occur there.
* **A small local LLM** (via [Ollama](https://ollama.com), default `gemma3:1b`) writes a one-or-two sentence field note. It is only given facts from `wihanga/endemics.json` and told not to add anything else, because small models invent things. With no Ollama running you get a plain static note instead. The app never depends on the LLM.
* **Trip log**: SQLite file on disk, exportable as CSV. Nothing is uploaded anywhere.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install tensorflow          # or tflite-runtime on Python 3.12 or older
python run.py                   # open http://127.0.0.1:5000
```

Just want to see the UI? No TensorFlow needed, the demo mode returns canned detections:

```bash
pip install -r requirements-dev.txt
python run.py --demo
```

### Optional: field notes from a local LLM

```bash
ollama pull gemma3:1b
ollama serve                    # then tick "Field notes" in the app
# use another model:  WIHANGA_MODEL=qwen2.5:1.5b python run.py
```

### Using it from a phone

Browsers only allow the microphone on `localhost` or HTTPS, so for a phone:

```bash
pip install cryptography
python run.py --host 0.0.0.0 --https
```

Open `https://<laptop-ip>:5000` on the phone and accept the self-signed certificate warning. This needs a local network between the two devices, not internet access. All audio processing still happens on the laptop; the phone is just a microphone and a speaker.

**Screen-off limitation:** mobile browsers pause the microphone when the screen locks. The app asks for a screen wake lock, and *Pocket mode* dims the screen to near-black so you can carry the phone while it keeps listening. A native app could go further; this one is a web page.

## What BirdNET can and can't hear

BirdNET 2.4 does **not** cover every Sri Lankan endemic. `python tools/check_coverage.py` compares our seed list with the model's labels: **15 of the 28 listed endemics are covered**. The missing ones are mostly hill-country and rainforest specialists (Yellow-eared Bulbul, Dull-blue Flycatcher, Sri Lanka Bush Warbler, Serendib Scops-Owl and others). Those would need a custom classifier, which `birdnetlib` supports but this project does not include yet. See *Contributing*.

The seed list in `endemics.json` is hand-written and not exhaustive. Please check zones and notes against a local field guide.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests use a fake identifier, so they run without TensorFlow. The real BirdNET path was run separately end to end on synthetic audio (silence and noise at 44.1 and 48 kHz). That checks the plumbing, not bird-ID accuracy.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No matching distribution found for tflite-runtime` | No wheels for Python 3.13. Use `pip install tensorflow`. |
| `No module named 'pyaudioop'` / `audioread` | `pip install audioop-lts audioread` (already in `requirements.txt`). |
| "Microphone unavailable" on a phone | Open the page over HTTPS (`--https`), not plain HTTP. |
| Stops listening when the phone locks | Keep the screen on; use Pocket mode. |
| Notes say "static (LLM off)" | Ollama isn't running or the model isn't pulled. |
| 503 "BirdNET is not installed" | Install the TensorFlow/BirdNET deps, or run with `--demo`. |

## Contributing

Good first issues:

* **Sinhala names**: fill in `name_si` in `wihanga/endemics.json` (all `null` right now).
* **Verify and extend** the endemic list: zones, notes, missing species.
* **Custom classifier** for the 13 endemics BirdNET misses, trained on openly licensed recordings (for example from Xeno-canto, check each recording's licence), loaded through `birdnetlib`'s custom classifier support.
* Real-world field reports: what it got right and wrong on the trail.

## Licences

* BirdNET model files: **CC BY-NC-SA 4.0 (non-commercial)**, from [BirdNET-Analyzer](https://github.com/kahst/BirdNET-Analyzer). They are open weights, but you cannot use them in a commercial product.
* `birdnetlib`: Apache-2.0.
* This project's own code: add a licence file of your choice before publishing.
