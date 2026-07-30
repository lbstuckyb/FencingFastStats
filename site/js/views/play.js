// `#/play` — a side-view piste duel, the one page here that isn't analytics.
//
// Épée: whole body is target, no right-of-way, so two blades landing together
// is a double — a touch for you and a life gone. Backing over your own rear
// limit concedes a touch, which is what stops retreating from being a strategy.
// Scored like the offline dino game: one endless run, three lives, a high score
// in localStorage.
//
// Lifecycle is the one thing this view has to do that no other view does. The
// router in app.js has no teardown hook, so the run stops itself: the frame
// loop exits as soon as the canvas leaves the document, a `hashchange` listener
// stops it the moment a navigation starts, and `visibilitychange` pauses a
// hidden tab rather than letting it burn frames. `stop()` removes every
// listener it added, including the input module's.

import { el } from "../util.js";
import { CONFIG, createGame, startRun, step } from "../game/engine.js";
import { attach, CONTROLS } from "../game/input.js";
import { HEIGHT, WIDTH, draw, readPalette } from "../game/render.js";

const HIGH_SCORE_KEY = "ffs-play-best";

function readBest() {
  const raw = Number(localStorage.getItem(HIGH_SCORE_KEY));
  return Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : 0;
}

function writeBest(score) {
  try { localStorage.setItem(HIGH_SCORE_KEY, String(score)); } catch { /* private mode */ }
}

const KEY_TABLE = [
  ["← →", "Retreat / advance along the piste"],
  ["A", "Attack — short reach, quick recovery"],
  ["D", "Défense — parry. Catching the blade opens a riposte window"],
  ["F", "Fente — lunge. Long reach, slow to recover from"],
  ["Space", "Bond en arrière — jump back out of distance"],
];

function rules() {
  return el("details", { class: "table-view game-rules" }, [
    el("summary", { text: "Rules and controls" }),
    el("div", { class: "prose" }, [
      el("p", { text: "Épée: the whole body is target and there is no right of way. If both blades land in the same moment it is a double touch — you score a point and you lose a life. Three lives; the run ends on the third touch against you." }),
      el("p", { text: "Your rear limit is the hatched line behind you. Cross it and you concede a penalty touch, so retreating is never free. A parry that catches the blade opens a short riposte window: an attack thrown inside it is fast and cannot be doubled." }),
      el("p", { text: `A fresh opponent arrives every ${CONFIG.boutTouches} touches, and each one reacts faster than the last.` }),
      el("table", {}, [
        el("thead", {}, [el("tr", {}, [el("th", { text: "Key" }), el("th", { text: "Action" })])]),
        el("tbody", {}, KEY_TABLE.map(([key, what]) =>
          el("tr", {}, [
            el("td", { class: "nowrap" }, [el("code", { text: key })]),
            el("td", { class: "small", text: what }),
          ]))),
      ]),
      el("p", { class: "small muted", text: "This page is a diversion — nothing on it comes from the FIE dataset the rest of the site is built on." }),
    ]),
  ]);
}

export async function render() {
  const state = createGame({ seed: (Date.now() & 0x7fffffff) || 1 });
  let best = readBest();

  // ---- DOM ----------------------------------------------------------------

  const canvas = el("canvas", {
    class: "game-canvas",
    width: WIDTH,
    height: HEIGHT,
    role: "img",
    "aria-label": "A side view of a fencing piste with two fencers en garde.",
  });

  const scoreOut = el("strong", { text: "0" });
  const livesOut = el("strong", { text: String(CONFIG.lives) });
  const bestOut = el("strong", { text: String(best) });
  const hud = el("div", { class: "game-hud" }, [
    el("span", {}, ["Touches ", scoreOut]),
    el("span", {}, ["Lives ", livesOut]),
    el("span", { class: "muted" }, ["Best ", bestOut]),
    el("span", { class: "muted game-side", text: "You are the fencer on the left, facing right." }),
  ]);

  // The canvas is decorative to a screen reader; this line is the game.
  const status = el("p", { class: "small muted game-status", role: "status", "aria-live": "polite", text: "Press start to begin." });

  const overlayTitle = el("h2", { text: "Piste duel" });
  const overlayBody = el("p", { class: "small", text: "Three lives. Every touch you land is a point. A double costs you one." });
  const overlayButton = el("button", { type: "button", class: "game-button", text: "Start" });
  const overlay = el("div", { class: "game-overlay" }, [overlayTitle, overlayBody, overlayButton]);

  const pad = el("div", { class: "game-pad", role: "group", "aria-label": "Touch controls" },
    CONTROLS.map((c) => el("button", {
      type: "button", "data-game-key": c.key, "aria-label": c.name, title: c.name,
    }, [el("span", { "aria-hidden": "true", text: c.label })])));

  const stage = el("div", { class: "game-stage" }, [canvas, overlay]);
  const surface = el("div", { class: "game-surface" }, [hud, stage, pad, status]);

  const page = el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Piste duel" }),
      el("p", { class: "muted", text: "A small épée game. No data, no ratings — just distance, tempo and the back line." }),
    ]),
    el("div", { class: "card" }, [surface, rules()]),
  ]);

  // ---- loop ---------------------------------------------------------------

  const ctx = canvas.getContext("2d");
  let palette = readPalette(document.documentElement);
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

  // The backing store follows the layout, not the constants: `draw()` works in
  // the 320x180 space and scales onto whatever is here, so the salle is vector
  // line art at device resolution instead of a small buffer blown up by CSS.
  // Capped at 3x because past that the extra pixels cost fill rate and buy
  // nothing a display can show.
  function resize(width) {
    if (!(width > 0)) return false;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const w = Math.round(width * dpr);
    const h = Math.round((w * HEIGHT) / WIDTH);
    if (w === canvas.width && h === canvas.height) return false;
    canvas.width = w;
    canvas.height = h;
    return true;
  }

  // Changing the backing store clears the canvas, so a paused or finished run
  // has to be redrawn by hand — the frame loop isn't running to do it.
  function resized(width) {
    if (!resize(width) || raf || stopped) return;
    draw(ctx, state, palette, { reducedMotion: motionQuery.matches });
  }

  const observer = new ResizeObserver((entries) => {
    for (const entry of entries) resized(entry.contentRect.width);
  });
  // The observer is the general case; this is the common one. Observer
  // callbacks are delivered in the rendering step, which a window that isn't
  // painting doesn't reach — a plain resize event still does.
  const onResize = () => resized(canvas.clientWidth);

  const isLive = () => state.phase === "playing";
  const { input, detach } = attach(surface, isLive);

  let raf = 0;
  let previous = 0;
  let stopped = false;
  let announceAt = 0;

  function setOverlay(title, body, label) {
    if (title === null) {
      overlay.hidden = true;
      return;
    }
    overlayTitle.textContent = title;
    overlayBody.textContent = body;
    overlayButton.textContent = label;
    overlay.hidden = false;
  }

  function syncHud() {
    scoreOut.textContent = String(state.score);
    livesOut.textContent = String(state.lives);
    bestOut.textContent = String(best);
    canvas.setAttribute(
      "aria-label",
      `Fencing piste. ${state.score} touches scored, ${state.lives} lives left, against ${state.opponentName}.`
    );
  }

  // An aria-live region that spoke every frame would be unusable, so only real
  // events and at most one message every 900ms reach it.
  function announce(text, force = false) {
    const now = performance.now();
    if (!force && now - announceAt < 900) return;
    announceAt = now;
    status.textContent = text;
  }

  function handleEvents() {
    for (const event of state.events) {
      if (event.type === "over") {
        if (state.score > best) { best = state.score; writeBest(best); }
        syncHud();
        setOverlay(
          "Run over",
          `${state.score} ${state.score === 1 ? "touch" : "touches"} · best ${best}.`,
          "Fence again"
        );
        announce(`${state.last} Best ${best}.`, true);
        return;
      }
      if (event.type === "touch" || event.type === "newbout") {
        syncHud();
        announce(event.type === "newbout" ? `New opponent: ${event.name}.` : state.last, true);
      }
    }
  }

  function frame(now) {
    raf = 0;
    // Belt one: the router replaced `main`, so this canvas is orphaned. Nothing
    // else will tell us — there is no teardown hook to hang it on.
    if (stopped || !canvas.isConnected) { stop(); return; }
    // Belt one and a half. `ResizeObserver` notifications are delivered in the
    // same rendering step as this callback, so anything that suppresses that
    // step suppresses both — and the canvas would then be drawing into a
    // backing store the layout has already moved on from. The read is off a
    // leaf element that nothing here reflows, so it costs nothing.
    resize(canvas.clientWidth);

    const dt = previous ? now - previous : 0;
    previous = now;

    if (state.phase === "playing") {
      const action = input.take();
      step(state, dt, { left: input.left, right: input.right, action });
      if (state.events.length) handleEvents();
      if (state.phase === "playing" && state.score !== Number(scoreOut.textContent)) syncHud();
    }
    draw(ctx, state, palette, { reducedMotion: motionQuery.matches });
    // Paused and finished runs draw their last frame and then let the loop
    // die; `run()` is what brings it back.
    if (state.phase === "playing") raf = requestAnimationFrame(frame);
  }

  function run() {
    if (raf || stopped) return;
    previous = 0;
    raf = requestAnimationFrame(frame);
  }

  function begin() {
    startRun(state, (Date.now() & 0x7fffffff) || 1);
    input.clear();
    syncHud();
    setOverlay(null);
    announce("En garde. Allez.", true);
    run();
  }

  function pause() {
    if (state.phase !== "playing") return;
    state.phase = "paused";
    input.clear();
    setOverlay("Paused", "The bout is on hold.", "Resume");
    announce("Paused.", true);
  }

  function stop() {
    if (stopped) return;
    stopped = true;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    detach();
    observer.disconnect();
    window.removeEventListener("resize", onResize);
    window.removeEventListener("hashchange", onHashChange);
    window.removeEventListener("ffs:themechange", onTheme);
    document.removeEventListener("visibilitychange", onVisibility);
    darkQuery.removeEventListener("change", onTheme);
  }

  // Belt two: fires the moment a navigation starts, before the router has even
  // swapped the DOM — so no frame ever runs against a detached canvas.
  const onHashChange = () => stop();
  // Belt three: a hidden tab gets one giant dt on return; pausing is both
  // kinder to the battery and fairer to the player.
  const onVisibility = () => { if (document.hidden) pause(); };
  const onTheme = () => {
    palette = readPalette(document.documentElement);
    if (!raf && !stopped) draw(ctx, state, palette, { reducedMotion: motionQuery.matches });
  };

  window.addEventListener("hashchange", onHashChange);
  window.addEventListener("ffs:themechange", onTheme);
  document.addEventListener("visibilitychange", onVisibility);
  darkQuery.addEventListener("change", onTheme);
  window.addEventListener("resize", onResize);
  observer.observe(canvas);

  overlayButton.addEventListener("click", () => {
    if (state.phase === "paused") {
      state.phase = "playing";
      setOverlay(null);
      announce("Resumed.", true);
      run();
      return;
    }
    begin();
  });

  // One frame now, so the piste is drawn behind the start overlay rather than
  // the page showing an empty box until the first click.
  draw(ctx, state, palette, { reducedMotion: motionQuery.matches });
  syncHud();

  return page;
}
