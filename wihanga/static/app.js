"use strict";

const CHUNK_SEC = 6;            // audio sent to BirdNET in 6 s pieces (two 3 s windows)
const REANNOUNCE_MS = 120000;   // don't repeat the same bird's name within 2 minutes
const MAX_CARDS = 20;

const $ = (sel) => document.querySelector(sel);
const el = {
  listen: $("#listen"), status: $("#status"), heard: $("#heard"),
  speak: $("#opt-speak"), notes: $("#opt-notes"), si: $("#opt-si"), dim: $("#opt-dim"),
  chipModel: $("#chip-model"), chipLlm: $("#chip-llm"),
  log: $("#log"), logBody: $("#log-body"),
};

const st = {
  on: false, ctx: null, stream: null, src: null, proc: null,
  chunks: [], samples: 0, wake: null, pos: null,
  queue: [], busy: false,
  lastSeen: new Map(), cards: new Map(),
};

function setStatus(text) { el.status.textContent = text; }

// ---------- server health chips ----------
async function loadHealth() {
  try {
    const j = await (await fetch("/api/health")).json();
    el.chipModel.textContent = "model: " + j.identifier;
    el.chipModel.classList.add("ok");
    el.chipLlm.textContent = j.llm ? "notes: " + j.model : "notes: static (LLM off)";
    el.chipLlm.classList.toggle("ok", j.llm);
  } catch (_) {
    el.chipModel.textContent = "server unreachable";
  }
}

// ---------- audio capture ----------
function encodeWav(samples, rate) {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const str = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };
  str(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  str(36, "data"); view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}

function flush() {
  const all = new Float32Array(st.samples);
  let off = 0;
  for (const c of st.chunks) { all.set(c, off); off += c.length; }
  st.chunks = []; st.samples = 0;
  st.queue.push(encodeWav(all, st.ctx.sampleRate));
  if (st.queue.length > 3) st.queue.shift();   // never let a slow server build a backlog
  pump();
}

async function pump() {
  if (st.busy) return;
  st.busy = true;
  while (st.queue.length) {
    try { await identify(st.queue.shift()); }
    catch (e) { if (st.on) setStatus("Problem: " + e.message); }
  }
  st.busy = false;
}

async function identify(wav) {
  const body = new FormData();
  body.append("audio", wav, "chunk.wav");
  if (st.pos) { body.append("lat", st.pos.lat); body.append("lon", st.pos.lon); }
  const res = await fetch("/api/identify", { method: "POST", body });
  const j = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(j.error || "HTTP " + res.status);
  if (!st.on) return;
  setStatus(j.detections.length
    ? "Listening. Last heard: " + j.detections[0].common_name
    : "Listening. Nothing clear yet.");
  j.detections.forEach(handleDetection);
}

// ---------- detections ----------
function say(text) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.95;
  window.speechSynthesis.speak(u);
}

function makeCard(d) {
  const root = document.createElement("li");
  root.className = "card" + (d.endemic ? " endemic" : "");
  const top = document.createElement("div"); top.className = "card-top";
  const left = document.createElement("div");
  const name = document.createElement("span"); name.className = "name"; name.textContent = d.common_name;
  left.appendChild(name);
  if (d.endemic) {
    const b = document.createElement("span"); b.className = "badge"; b.textContent = "Endemic";
    left.appendChild(b);
  }
  const conf = document.createElement("span"); conf.className = "conf";
  top.append(left, conf);
  const sci = document.createElement("div"); sci.className = "sci"; sci.textContent = d.scientific_name;
  const note = document.createElement("p"); note.className = "note"; note.hidden = true;
  root.append(top, sci, note);
  return { root, conf, note };
}

async function loadNote(d, card) {
  const lang = el.si.checked ? "si" : "en";
  const q = new URLSearchParams({ sci: d.scientific_name, name: d.common_name, lang });
  try {
    const j = await (await fetch("/api/note?" + q)).json();
    card.note.textContent = j.text;
    card.note.dataset.source = j.source;
    card.note.hidden = false;
  } catch (_) { /* notes are optional */ }
}

function handleDetection(d) {
  const now = Date.now();
  const last = st.lastSeen.get(d.scientific_name) || 0;
  let card = st.cards.get(d.scientific_name);
  if (!card || now - last > REANNOUNCE_MS) {
    card = makeCard(d);
    st.cards.set(d.scientific_name, card);
    el.heard.prepend(card.root);
    while (el.heard.children.length > MAX_CARDS) el.heard.lastElementChild.remove();
    if (el.speak.checked) say(d.endemic ? "Endemic. " + d.common_name : d.common_name);
    if (el.notes.checked) loadNote(d, card);
  }
  st.lastSeen.set(d.scientific_name, now);
  card.conf.textContent = Math.round(d.confidence * 100) + "%";
}

// ---------- start / stop ----------
async function keepAwake() {
  try { if ("wakeLock" in navigator) st.wake = await navigator.wakeLock.request("screen"); }
  catch (_) { /* not fatal */ }
}
document.addEventListener("visibilitychange", () => {
  if (st.on && document.visibilityState === "visible") keepAwake();
});

function locate() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    (p) => { st.pos = { lat: p.coords.latitude, lon: p.coords.longitude }; },
    () => {},   // no GPS fix: the server falls back to central Sri Lanka
    { maximumAge: 600000, timeout: 8000 },
  );
}

async function start() {
  try {
    st.stream = await navigator.mediaDevices.getUserMedia({
      // Browser "voice" processing smears bird calls, so switch it all off.
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
    });
  } catch (_) {
    setStatus("Microphone unavailable. On a phone this page must be opened over HTTPS (or localhost).");
    return;
  }
  st.ctx = new (window.AudioContext || window.webkitAudioContext)();
  st.src = st.ctx.createMediaStreamSource(st.stream);
  st.proc = st.ctx.createScriptProcessor(4096, 1, 1);   // deprecated but works in every browser
  const mute = st.ctx.createGain(); mute.gain.value = 0;
  st.chunks = []; st.samples = 0;
  st.proc.onaudioprocess = (e) => {
    const data = e.inputBuffer.getChannelData(0);
    st.chunks.push(new Float32Array(data));
    st.samples += data.length;
    if (st.samples >= st.ctx.sampleRate * CHUNK_SEC) flush();
  };
  st.src.connect(st.proc); st.proc.connect(mute); mute.connect(st.ctx.destination);
  locate(); keepAwake();
  st.on = true;
  el.listen.classList.add("on"); el.listen.setAttribute("aria-pressed", "true"); el.listen.textContent = "Stop";
  setStatus("Listening. You can put the phone away and look up.");
}

function stop() {
  st.on = false;
  try { st.proc.disconnect(); st.src.disconnect(); } catch (_) {}
  if (st.stream) st.stream.getTracks().forEach((t) => t.stop());
  if (st.ctx) st.ctx.close();
  if (st.wake) { st.wake.release().catch(() => {}); st.wake = null; }
  st.queue = [];
  el.listen.classList.remove("on"); el.listen.setAttribute("aria-pressed", "false"); el.listen.textContent = "Listen";
  setStatus("Stopped. Your sightings are saved in the trip log.");
}

el.listen.addEventListener("click", () => (st.on ? stop() : start()));
el.dim.addEventListener("change", () => document.body.classList.toggle("dim", el.dim.checked));

// ---------- trip log ----------
el.log.addEventListener("toggle", async () => {
  if (!el.log.open) return;
  const j = await (await fetch("/api/sightings")).json();
  const table = document.createElement("table");
  table.innerHTML = "<tr><th>Time</th><th>Bird</th><th>Conf.</th></tr>";
  for (const s of j.sightings) {
    const tr = document.createElement("tr");
    [s.ts.replace("T", " "), s.common_name + (s.endemic ? " ★" : ""), Math.round(s.confidence * 100) + "%"]
      .forEach((t) => { const td = document.createElement("td"); td.textContent = t; tr.appendChild(td); });
    table.appendChild(tr);
  }
  el.logBody.replaceChildren(j.sightings.length ? table : document.createTextNode("No sightings yet."));
});

loadHealth();
