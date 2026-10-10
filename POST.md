---
title: Wihanga Nada: an offline bird-call identifier for Sri Lanka
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)*

## What I Built

Wihanga Nada ("sounds of birds") is a bird-call identifier for Sri Lanka that works with no signal and no account. You tap **Listen** once, put the phone away, and look up. It listens in 6-second pieces, says the bird's name out loud, flags Sri Lankan endemics, and keeps a trip log you can export as CSV.

The goal was to make the screen the shortest part of the experience. If the app does its job, you spend the walk watching the canopy, not reading a phone. The best birding places here (Sinharaja, Horton Plains, Yala) are also the places with the worst mobile signal, so "works offline" is not a nice-to-have.

It is for anyone who wants to put names to the sounds around them, from first-time walkers to people who already carry binoculars.

## Demo

There is no deployed link, on purpose: the whole point is that it runs on your own machine without the internet. To try it in two minutes, with no TensorFlow and no model download:

```bash
pip install -r requirements-dev.txt
python run.py --demo
# open http://127.0.0.1:5000
```

Demo mode returns canned detections so you can see the interface. It does not listen to the audio. The real identifier is `python run.py` after installing `requirements.txt` and `tensorflow`.

## Code

{% github YOUR-GITHUB-USERNAME/wihanga-nada %}

## How I Built It

* **BirdNET 2.4** (through the `birdnetlib` package) does the identification. The model files ship inside the pip package, so after install it needs no network. I pass GPS (or central Sri Lanka as a fallback) and the date, and BirdNET narrows its candidates to species that can occur there.
* **A small local LLM through Ollama** (default `gemma3:1b`, swappable with one environment variable) writes the field notes. Small models make things up, so it never answers from memory: it only gets facts from my own `endemics.json` and is told to add nothing else. If Ollama isn't running, the app falls back to a static note built from the same facts, so it never depends on the LLM. Birds that aren't in my verified list are never sent to the model at all.
* **Flask and a plain web page.** The page records the microphone, switches off the browser's voice processing (echo cancellation and noise suppression smear bird calls), encodes WAV chunks, and speaks the results with the browser's built-in speech synthesis. A screen wake lock and a dim "pocket mode" keep it listening while you walk.
* **SQLite** for the trip log, with de-duplication so one bird singing for a minute is one sighting, not ten.
* I built it with Claude as my coding assistant.

What I checked: BirdNET's own label file (to see which Sri Lankan endemics it can actually name), that the real BirdNET path runs end to end on synthetic audio at both 44.1 and 48 kHz (in well under a second per chunk on my test machine), that the HTTP and HTTPS servers respond, and 14 automated tests.

Limits, stated plainly:

* **BirdNET 2.4 covers only 15 of the 28 endemics in my seed list.** Hill-country specialists such as the Yellow-eared Bulbul, Dull-blue Flycatcher and Sri Lanka Bush Warbler, and the Serendib Scops-Owl, are not in the model, so the app cannot name them yet. A small script (`tools/check_coverage.py`) reports this gap instead of hiding it.
* **I have not yet measured identification accuracy on real recordings in the field.** My end-to-end run used synthetic silence and noise, which checks the plumbing, not whether it names birds correctly.
* **Mobile browsers pause the microphone when the screen locks.** The wake lock and pocket mode work around it, but a native app would do better.
* `tflite-runtime` has no wheels for Python 3.13 and `birdnetlib` needs `audioop-lts` there, so the README documents the install path that worked.

## Why Does Open Innovation Matter?

* **No signal, no problem.** A closed audio-ID API needs a connection, and the best birding spots here have none. Open weights run on the laptop in the bag.
* **Data stays with the person.** Recordings and sightings never leave the machine. That matters when a sighting log can reveal where a rare, poachable bird lives.
* **I can swap pieces.** The LLM is one environment variable. The identifier sits behind a tiny interface, so another model can replace BirdNET.
* **The gaps are fixable.** With a closed API, a missing species is a feature request. Here, the 13 endemics BirdNET misses are an open to-do: `birdnetlib` supports custom classifiers, so a community can train on openly licensed recordings and add them. I haven't done that yet, so I list it as the next step, not a feature.
* **It costs nothing to run.** No API key and no per-call fee.

One honest caveat: the BirdNET model files are CC BY-NC-SA 4.0. They are open weights, but non-commercial. That suits a community hiking tool and not a paid product, and anyone building on this should know it.
