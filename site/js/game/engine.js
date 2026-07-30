// The piste-duel rule set: DOM-free, deterministic, and the only place the
// game's behaviour lives. `render.js` draws whatever this produces and never
// decides anything; `views/play.js` owns the frame loop and the page.
//
// Being DOM-free is deliberate — it means a scripted match can be run straight
// through node, with no browser, to check the invariants that a screenshot
// can't see (lives only fall, score only rises, a double moves both, the run
// always ends).
//
// Épée rules: whole body is target and there is no right-of-way, so a blade
// arriving inside the other's lockout window is a *double* — a touch for you
// and a life gone. The rear piste limit is a penalty touch, which is what
// stops backing away from being a winning strategy.

// ---- tunables --------------------------------------------------------------
// Distances are canvas-width units (the piste is drawn 1:1 into a 320-wide
// canvas); times are milliseconds. Everything here is meant to be tuned by
// feel — the numbers are one object so tuning never means hunting through code.

export const CONFIG = {
  // `gap` is the en garde distance, and it must stay *wider* than the longest
  // reach below: if a lunge lands from the reset position, the whole game
  // collapses into mashing lunge off every restart, and a player who holds
  // distance is forced backwards into their own limit from the first frame.
  piste: { left: 24, right: 296, centre: 160, gap: 70 },
  // Fencers can't walk through each other; this is the closest they stand.
  minGap: 19,
  advanceSpeed: 0.078, // units/ms
  retreatSpeed: 0.068,
  jumpDistance: 44,
  lives: 3,
  // The épée lockout. A landed touch doesn't score on its own tick: the box
  // stays open this long, and a blade arriving inside it makes the exchange a
  // double. Without it the two blades have to go active on the *same* frame,
  // which happens ~1% of the time and leaves the double — the rule the whole
  // risk model rests on — as decoration.
  lockoutMs: 90,
  // How long both fencers stand reset between touches. Input is ignored during
  // it, which is also what stops a rear-limit penalty firing twice.
  resetMs: 750,
  riposteMs: 400,
  boutTouches: 5, // a fresh opponent every this many touches
  // The dino-game escalation: by `rampTouches` the opponent is at full speed.
  rampTouches: 20,
  reaction: [420, 140], // ms between decisions, easy -> hard
  windupScale: [1, 0.65], // multiplier on the opponent's windup, easy -> hard
  parryChance: [0.25, 0.55],
};

// windup -> active -> recovery. A touch lands only on `active` frames, and only
// when the tip reaches the other body — that's the whole distance game.
export const ACTIONS = {
  attack: { windup: 90, active: 80, recovery: 160, reach: 32 },
  // The reward for a parry: the same attack, but half the windup, and immune
  // to being doubled.
  riposte: { windup: 40, active: 80, recovery: 110, reach: 32 },
  lunge: { windup: 150, active: 110, recovery: 300, reach: 52 },
  // The parry's active window has to outlast the longest windup above, or a
  // parry thrown the moment you see the tell expires before the blade ever
  // arrives and the defence is decorative. 220 > lunge's 150 with room to
  // spare; the 280ms whiff recovery is what keeps it from being free.
  parry: { windup: 0, active: 220, recovery: 280 },
  jumpback: { windup: 0, active: 180, recovery: 300 },
  recoil: { windup: 0, active: 0, recovery: 420 }, // being parried
};

// Exported so `render.js` doesn't keep a second copy that can drift: it needs
// to know when a blade is in flight to draw the trail behind it.
export const BLADE_ACTIONS = new Set(["attack", "riposte", "lunge"]);

export const OPPONENTS = [
  "Bout 1 · the club captain",
  "Bout 2 · the left-hander",
  "Bout 3 · the counter-attacker",
  "Bout 4 · the metronome",
  "Bout 5 · the finalist",
  "Bout 6 · the world champion",
];

// ---- rng -------------------------------------------------------------------
// xorshift32: four lines, no dependency, and the same seed replays the same
// match — which is what makes the headless harness reproducible.

function rng(seed) {
  let s = (seed >>> 0) || 0x9e3779b9;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
const lerp = (a, b, t) => a + (b - a) * t;

// ---- state -----------------------------------------------------------------

function makeFencer(side) {
  const dir = side === "player" ? 1 : -1;
  return {
    side,
    dir, // +1 faces right, -1 faces left
    x: CONFIG.piste.centre - (dir * CONFIG.piste.gap) / 2,
    action: "garde",
    phase: "idle",
    t: 0, // ms elapsed in the current phase
    move: 0, // -1 retreat, 0 still, +1 advance
    moveFor: 0, // opponent only: ms left of the current walk
    didHit: false, // one touch per blade action
    riposte: 0, // ms left of the riposte window
    windupScale: 1,
    think: 0, // opponent only: ms to the next decision
    punish: 0, // opponent only: cooldown on the counter-into-recovery read
  };
}

export function createGame({ seed = 1 } = {}) {
  const state = {
    seed,
    rand: rng(seed),
    phase: "ready", // ready | playing | paused | over
    time: 0,
    score: 0,
    lives: CONFIG.lives,
    bout: 0,
    opponentName: OPPONENTS[0],
    lock: null, // the open lockout box, if a touch has just landed
    freeze: 0, // ms left of the between-touches reset
    flash: 0, // ms left of the touch flash (render only)
    lamp: null, // who the apparatus lit for (render only): player | opponent | both
    shake: 0,
    events: [], // consumed by the view each frame
    last: "En garde.",
    player: makeFencer("player"),
    opponent: makeFencer("opponent"),
  };
  applyDifficulty(state);
  return state;
}

/** Restarts an existing state in place, so the view can reuse its canvas. */
export function startRun(state, seed = state.seed) {
  const fresh = createGame({ seed });
  for (const key of Object.keys(fresh)) state[key] = fresh[key];
  state.phase = "playing";
  return state;
}

function applyDifficulty(state) {
  const t = clamp(state.score / CONFIG.rampTouches, 0, 1);
  state.difficulty = t;
  state.reactionMs = lerp(CONFIG.reaction[0], CONFIG.reaction[1], t);
  state.opponent.windupScale = lerp(CONFIG.windupScale[0], CONFIG.windupScale[1], t);
  state.parryChance = lerp(CONFIG.parryChance[0], CONFIG.parryChance[1], t);
}

// ---- action machinery ------------------------------------------------------

/** Duration of `phase` for `f`'s current action, in ms. Exported for `poses.js`. */
export function phaseDuration(f, phase = f.phase) {
  const spec = ACTIONS[f.action];
  if (!spec) return 0;
  const base = spec[phase] ?? 0;
  return phase === "windup" ? base * f.windupScale : base;
}

function begin(f, action) {
  f.action = action;
  f.phase = ACTIONS[action].windup > 0 ? "windup" : "active";
  f.t = 0;
  f.didHit = false;
  f.move = 0;
  f.moveFor = 0;
}

function toGarde(f) {
  f.action = "garde";
  f.phase = "idle";
  f.t = 0;
  f.didHit = false;
}

function advanceAction(f, dt) {
  if (f.action === "garde") return;
  f.t += dt;
  // A `while` rather than an `if`: a long frame can cross two short phases, and
  // skipping one would leave a blade permanently active.
  for (let guard = 0; guard < 8; guard += 1) {
    const d = phaseDuration(f);
    if (f.t < d) break;
    f.t -= d;
    if (f.phase === "windup") f.phase = "active";
    else if (f.phase === "active") f.phase = "recovery";
    else { toGarde(f); break; }
  }
}

const isParrying = (f) => f.action === "parry" && f.phase === "active";

function pendingTouch(f, other) {
  if (f.didHit || f.phase !== "active" || !BLADE_ACTIONS.has(f.action)) return false;
  return Math.abs(f.x - other.x) <= ACTIONS[f.action].reach;
}

// ---- player input ----------------------------------------------------------

const ACTION_KEYS = { attack: "attack", parry: "parry", lunge: "lunge", jump: "jumpback" };

function applyInput(state, input) {
  const f = state.player;
  f.move = 0;
  if (state.freeze > 0) return;
  if (f.action === "garde") {
    if (input.left && !input.right) f.move = -1;
    else if (input.right && !input.left) f.move = 1;
  }
  const wanted = ACTION_KEYS[input.action];
  if (!wanted || f.action !== "garde") return;
  // A parry buys the riposte, and the riposte is the only thing that beats a
  // simultaneous attack — so `a` inside the window means something different.
  if (wanted === "attack" && f.riposte > 0) begin(f, "riposte");
  else begin(f, wanted);
}

// ---- opponent --------------------------------------------------------------

function thinkOpponent(state, dt) {
  const o = state.opponent;
  const p = state.player;
  o.think -= dt;
  o.punish -= dt;
  if (o.moveFor > 0) {
    o.moveFor -= dt;
    if (o.moveFor <= 0) { o.moveFor = 0; o.move = 0; }
  }
  if (o.action !== "garde") return;

  const dist = Math.abs(o.x - p.x);

  // The one read that doesn't wait on the decision timer. A blade still
  // recovering is the easiest opening in fencing to see, and without this a
  // player who simply holds the lunge key scores almost as well as one who
  // fences — the recovery cost printed in ACTIONS has to actually be charged.
  const exposed =
    (BLADE_ACTIONS.has(p.action) && p.phase === "recovery") ||
    (p.action === "parry" && p.phase === "recovery") ||
    p.action === "recoil";
  if (exposed && o.punish <= 0 && dist <= ACTIONS.lunge.reach) {
    const act = dist <= ACTIONS.attack.reach ? "attack" : "lunge";
    // Only commit if the blade will still find the opening when it gets there.
    // Launching into the *tail* of a recovery is what makes the bout resonate:
    // the blade arrives exactly as the next parry comes out, is caught, the
    // recoil takes the same time again, and neither fencer ever scores.
    const arrival = ACTIONS[act].windup * o.windupScale;
    if (arrival <= phaseDuration(p) - p.t) {
      o.punish = state.reactionMs;
      begin(o, act);
      return;
    }
  }

  if (o.think > 0) return;
  o.think = state.reactionMs * (0.7 + state.rand() * 0.6);
  const nearOwnLimit = CONFIG.piste.right - o.x < 34;
  const threatened =
    BLADE_ACTIONS.has(p.action) && p.phase !== "recovery" &&
    dist <= ACTIONS[p.action].reach + 8;
  const r = state.rand();

  const walk = (dirSign) => { o.move = dirSign; o.moveFor = 90 + state.rand() * 180; };

  // Never throw a blade into a parry that is already out. Without this the
  // bout livelocks: hold the parry key and the opponent attacks, is parried,
  // recoils, attacks again on the same beat, and the two resonate forever
  // with no touch ever landing. Waiting is also simply what a fencer does —
  // the parry expires into its 280ms recovery, and *that* is the opening.
  if (p.action === "parry" && p.phase === "active") {
    if (!nearOwnLimit && r < 0.6) walk(-1);
    return;
  }

  if (o.riposte > 0) { begin(o, "riposte"); return; }

  if (threatened) {
    if (r < state.parryChance) begin(o, "parry");
    else if (r < state.parryChance + 0.3 && !nearOwnLimit) begin(o, "jumpback");
    // Otherwise it takes the double on purpose. Épée fencers really do this.
    else begin(o, dist <= ACTIONS.attack.reach ? "attack" : "lunge");
    return;
  }
  if (dist <= ACTIONS.attack.reach) {
    // Never lunge from inside attack distance: at that range the lunge can be
    // neither slipped nor read, which is unfair rather than difficult — and a
    // fencer that close simply extends.
    if (r < 0.7 || nearOwnLimit) begin(o, "attack");
    else walk(-1);
    return;
  }
  if (dist <= ACTIONS.lunge.reach) {
    if (r < 0.45) begin(o, "lunge");
    else walk(1);
    return;
  }
  walk(1);
}

// ---- movement --------------------------------------------------------------

function moveFencer(f, dt) {
  if (f.action === "jumpback" && f.phase === "active") {
    f.x -= f.dir * (CONFIG.jumpDistance / ACTIONS.jumpback.active) * dt;
    return;
  }
  if (f.action !== "garde" || f.move === 0) return;
  const speed = f.move > 0 ? CONFIG.advanceSpeed : CONFIG.retreatSpeed;
  f.x += f.move * f.dir * speed * dt;
}

function separate(state) {
  const { player: p, opponent: o } = state;
  if (o.x - p.x < CONFIG.minGap) {
    const mid = (o.x + p.x) / 2;
    p.x = mid - CONFIG.minGap / 2;
    o.x = mid + CONFIG.minGap / 2;
  }
  // The rear limit is a penalty, not a wall, so only the far side clamps.
  p.x = Math.min(p.x, CONFIG.piste.right);
  o.x = Math.max(o.x, CONFIG.piste.left);
}

// ---- scoring ---------------------------------------------------------------

function grantRiposte(f) {
  f.riposte = CONFIG.riposteMs;
  toGarde(f);
}

function resetPositions(state) {
  const { player: p, opponent: o } = state;
  for (const f of [p, o]) {
    toGarde(f);
    f.move = 0;
    f.moveFor = 0;
    f.riposte = 0;
    f.think = state.reactionMs;
    f.x = CONFIG.piste.centre - (f.dir * CONFIG.piste.gap) / 2;
  }
  state.lock = null;
  state.freeze = CONFIG.resetMs;
}

/**
 * The single place a score or a life ever changes. `to` is who the touch is
 * awarded to: "player", "opponent" or "both" for a double.
 */
function awardTouch(state, to, reason) {
  if (to === "player" || to === "both") state.score += 1;
  if (to === "opponent" || to === "both") state.lives -= 1;
  state.flash = 240;
  state.lamp = to; // render only: which side of the apparatus lights up
  state.shake = to === "player" ? 90 : 160;
  state.events.push({ type: "touch", to, reason });
  state.last =
    to === "both" ? `Double touch — ${reason}. A point each way.`
      : to === "player" ? `Touch for you — ${reason}.`
        : `Touch against you — ${reason}.`;
  resetPositions(state);

  if (state.lives <= 0) {
    state.lives = 0;
    state.phase = "over";
    state.freeze = 0;
    state.events.push({ type: "over", score: state.score });
    state.last = `Run over at ${state.score} ${state.score === 1 ? "touch" : "touches"}.`;
    return;
  }
  const bout = Math.floor(state.score / CONFIG.boutTouches);
  if (bout !== state.bout) {
    state.bout = bout;
    state.opponentName = OPPONENTS[bout % OPPONENTS.length];
    state.events.push({ type: "newbout", name: state.opponentName });
  }
  applyDifficulty(state);
}

function resolveTouches(state) {
  const { player: p, opponent: o } = state;
  let hitP = pendingTouch(p, o);
  let hitO = pendingTouch(o, p);

  // A parry eats the blade it caught and buys the riposte window.
  if (hitP && isParrying(o)) {
    hitP = false; p.didHit = true; begin(p, "recoil"); grantRiposte(o);
    state.events.push({ type: "parry", by: "opponent" });
  }
  if (hitO && isParrying(p)) {
    hitO = false; o.didHit = true; begin(o, "recoil"); grantRiposte(p);
    state.events.push({ type: "parry", by: "player" });
  }
  if (!hitP && !hitO) return;
  if (hitP) p.didHit = true;
  if (hitO) o.didHit = true;

  // Open the box, or land inside one already open. Nothing scores yet.
  if (!state.lock) state.lock = { ms: CONFIG.lockoutMs, player: null, opponent: null };
  if (hitP) state.lock.player = p.action;
  if (hitO) state.lock.opponent = o.action;
}

/** Closes the lockout and turns whatever registered inside it into a touch. */
function closeLock(state, lock) {
  let { player: byPlayer, opponent: byOpponent } = lock;
  // The riposte's privilege: taking the blade first means the exchange is
  // yours, so a riposte inside the box is never a double.
  if (byPlayer && byOpponent) {
    if (byPlayer === "riposte" && byOpponent !== "riposte") byOpponent = null;
    else if (byOpponent === "riposte" && byPlayer !== "riposte") byPlayer = null;
  }
  const named = byPlayer || byOpponent;
  const reason = named === "lunge" ? "lunge" : named === "riposte" ? "riposte" : "attack";
  if (byPlayer && byOpponent) awardTouch(state, "both", "both lights");
  else if (byPlayer) awardTouch(state, "player", reason);
  else awardTouch(state, "opponent", reason);
}

function checkLimits(state) {
  const { player: p, opponent: o } = state;
  // Checked before the reset freeze can lapse, and `resetPositions` puts both
  // back at centre, so one crossing can never bill twice.
  if (p.x < CONFIG.piste.left) {
    awardTouch(state, "opponent", "you crossed your rear limit");
    return true;
  }
  if (o.x > CONFIG.piste.right) {
    awardTouch(state, "player", "they crossed their rear limit");
    return true;
  }
  return false;
}

// ---- the tick --------------------------------------------------------------

/**
 * Advances the match by `dtMs`. `input` is `{ left, right, action }`, where
 * `action` is a one-shot "attack" | "parry" | "lunge" | "jump" or null.
 * Returns `state`, mutated in place.
 */
export function step(state, dtMs, input = {}) {
  state.events.length = 0;
  if (state.phase !== "playing") return state;

  // A backgrounded tab hands back one enormous frame; clamping keeps the blade
  // phases and the collision test meaningful (and every number finite).
  const dt = clamp(Number.isFinite(dtMs) ? dtMs : 0, 0, 50);
  if (dt === 0) return state;

  state.time += dt;
  state.flash = Math.max(0, state.flash - dt);
  state.shake = Math.max(0, state.shake - dt);

  if (state.freeze > 0) {
    state.freeze = Math.max(0, state.freeze - dt);
    return state;
  }

  for (const f of [state.player, state.opponent]) {
    f.riposte = Math.max(0, f.riposte - dt);
  }

  applyInput(state, input);
  thinkOpponent(state, dt);

  advanceAction(state.player, dt);
  advanceAction(state.opponent, dt);

  moveFencer(state.player, dt);
  moveFencer(state.opponent, dt);
  separate(state);

  // A crossing during an open lockout is forgiven: the touch got there first,
  // and the reset that follows puts both fencers back at centre anyway.
  if (!state.lock && checkLimits(state)) return state;
  resolveTouches(state);

  if (state.lock) {
    state.lock.ms -= dt;
    if (state.lock.ms <= 0) {
      const lock = state.lock;
      state.lock = null;
      closeLock(state, lock);
    }
  }
  return state;
}
