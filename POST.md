---
title: Wihanga Nada: an offline bird-call identifier for Sri Lanka
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)*

## What I Built

<!-- TODO: edit the voice to sound like you. -->

Wihanga Nada ("sounds of birds") is a bird-call identifier for Sri Lanka that works with no signal and no account. You tap **Listen** once, put the phone away, and look up. It listens in 6-second pieces, says the bird's name out loud, flags Sri Lankan endemics, and keeps a trip log you can export as CSV.

The goal was to make the screen the shortest part of the experience. If the app is doing its job, you spend your time watching the canopy, not reading a phone. The places where birding is best here (Sinharaja, Horton Plains, Yala) are also the places where mobile signal is worst, so "works offline" is not a nice-to-have.

It is for anyone who wants to put names to the sounds around them, from first-time walkers to people already carrying binoculars.

## Demo

<!-- TODO: add a video or screen recording. Demo mode (`python run.py --demo`) is handy for a screen recording at home, but say clearly in the video that it uses canned results. -->

## How It Went Outside

<!-- TODO: fill this in with your REAL field test. Where did you go (for example the Negombo lagoon area)? How long? What did the app get right, what did it miss or get wrong, how did the phone and laptop setup feel on the trail? Honest notes beat a perfect story. Delete this section if you did not get outside. -->

## Code

<!-- TODO: embed the repo, e.g. {% github your-username/wihanga-nada %} -->

## How I Built It

* **BirdNET 2.4** (via the `birdnetlib` package) does the identification. The model files ship inside the pip package, so after install it needs no network. I pass GPS (or central Sri Lanka as a fallback) and the date, and BirdNET narrows its candidates to species that can occur there. For Sri Lanka it loaded a list of 263 species.
* **A small local LLM through Ollama** (default `gemma3:1b`, swappable with one environment variable) writes the field notes. Small models make things up, so it never answers from memory: it only gets facts from my own `endemics.json` and is told to add nothing else. If Ollama isn't running the app falls back to a static note built from the same facts, so it never depends on the LLM. Birds that aren't in my verified list never get sent to the model at all.
* **Flask + a plain web page.** The page records the microphone, switches off the browser's voice processing (echo cancellation and noise suppression smear bird calls), encodes WAV chunks, and speaks the results with the browser's built-in speech synthesis. A screen wake lock plus a dim "pocket mode" keep it listening while you walk.
* **SQLite** for the trip log, with de-duplication so one bird singing for a minute is one sighting, not ten.

Things I checked rather than assumed: the BirdNET model's label file (to see which Sri Lankan endemics it can actually name), that the real BirdNET path runs end to end on synthetic audio at both 44.1 and 48 kHz, and that the Flask endpoints behave (14 automated tests). On the CPU I tested on, a 6-second chunk took roughly a fifth of a second to analyse after warm-up.

What did not go smoothly: BirdNET 2.4 only covers **15 of the 28** endemics in my seed list. The hill-country specialists (Yellow-eared Bulbul, Dull-blue Flycatcher, Sri Lanka Bush Warbler) and the Serendib Scops-Owl are not in the model, so the app cannot name them yet. I wrote a small script (`tools/check_coverage.py`) that reports this gap instead of hiding it. Also, `tflite-runtime` has no wheels for Python 3.13 and `birdnetlib` needs `audioop-lts` there, so the README documents the install path that worked.

## Why Does Open Innovation Matter?

* **No signal, no problem.** A closed audio-ID API needs a connection, and the best birding spots here have none. Open weights run on the laptop in the bag.
* **Data stays with the person.** Recordings and sightings never leave the machine. That matters when a sighting log can reveal where a rare, poachable bird lives.
* **I can swap pieces.** The LLM is one environment variable. The identifier sits behind a tiny interface, so another model can replace BirdNET.
* **The gaps are fixable.** With a closed API, a missing species is a feature request. Here, the 13 endemics BirdNET misses are an open to-do: `birdnetlib` supports custom classifiers, so a community can train on openly licensed recordings and add them. I have not done this yet, and I list it as the next step rather than a feature.
* **Cost: nothing to run.** No API key, no per-call fee.

One honest caveat: the BirdNET model files are CC BY-NC-SA 4.0. They are open weights, but non-commercial. That is fine for a community hiking tool and not fine for selling it, and anyone building on this should know it.

## My Agent Session

<!-- Optional: save your session with DevRelay and embed it with the agent_session tag (see the challenge page), or link to it. -->

## Prize Categories

<!-- TODO: list the partner categories you are entering, or delete this section. -->
