// Keyframe pose tables for the two fencers.
//
// Coordinates are local to a fencer: origin at the feet on the piste, +x is the
// way they face, +y is up. `render.js` mirrors x by the fencer's direction and
// flips y into canvas space, so every pose here is written facing right.
//
// The poses **step** between keyframes instead of interpolating. That single
// choice is what gives the whole thing its Prince-of-Persia weight: the
// in-between frames are missing on purpose, so a lunge reads as a decision
// rather than a slide.
//
// **Drawn reach is derived, never typed.** A blade action's furthest tip comes
// from `ACTIONS[...].reach`, because the hit test is centre-to-centre against
// exactly that number (`engine.js`). Hard-coding it once already put en garde
// at full attack reach, which left the attack with nothing to extend into.

import { ACTIONS, phaseDuration } from "./engine.js";

// The tip at an action's maximum range. `- 2` lands the point on the front of
// the opponent's torso rather than through their spine: the engine measures
// centre to centre, so a tip drawn at exactly `reach` looks like it overshoots.
const tipAt = (action) => ACTIONS[action].reach - 2;

// The 12fps cadence the animation quantises to. Everything visible steps on
// this grid even though the frame loop runs at whatever the display gives us.
export const FRAME_MS = 1000 / 12;

// En garde is a *bent* arm: elbow tucked down by the ribs, forearm up and
// forward, point carried above the line. This is the pose that creates the
// room every extension below spends — draw the point out here and the attack
// has nowhere left to go.
//
// Two lengths hold roughly constant across the whole table, because an arm and
// a blade that change length between keyframes are what make a figure read as
// a puppet: **arm ~14 units** (shoulder → elbow → hand) and **blade ~13**
// (hand → tip). `lungeOut` is the one deliberate exception; see there.
const GARDE = {
  head: [0, 36],
  neck: [-1, 31],
  hip: [-2, 19],
  backKnee: [-8, 10],
  backFoot: [-11, 0],
  frontKnee: [7, 10],
  frontFoot: [11, 0],
  shoulder: [1, 30],
  elbow: [1, 23],
  hand: [8, 25],
  tip: [20, 30],
  rearElbow: [-8, 32],
  rearHand: [-11, 38],
};

// The resting height of the hips. `render.js` measures a fencer's lift off the
// piste against this to fade their contact shadow, so it has to come from the
// table rather than be typed twice.
export const GARDE_HIP = GARDE.hip[1];

// Poses are written as deltas from en garde so a keyframe only says what it
// changes — which is also how they stay readable as a table.
const pose = (overrides) => ({ ...GARDE, ...overrides });

const P = {
  garde: GARDE,
  // Idle isn't static: a 2-frame breath keeps a stopped fencer alive.
  breathe: pose({ head: [0, 35], neck: [-1, 30], shoulder: [1, 29], hand: [8, 24], tip: [20, 29] }),

  advance1: pose({ frontKnee: [9, 12], frontFoot: [14, 3], hip: [-1, 20] }),
  advance2: pose({ backKnee: [-6, 10], backFoot: [-8, 2], hip: [0, 19] }),
  retreat1: pose({ backKnee: [-10, 12], backFoot: [-15, 3], hip: [-4, 20] }),
  retreat2: pose({ frontKnee: [5, 10], frontFoot: [8, 2], hip: [-3, 19] }),

  // Attack: the hand coils back into a gather, then the whole arm straightens
  // — épée's whole point is that the hand leads. Shoulder → elbow → hand → tip
  // are near-collinear at `attackOut`, which is what makes the extension read
  // as one line rather than a tilt.
  attackWind: pose({ elbow: [0, 22], hand: [6, 24], tip: [17, 31], hip: [-3, 19] }),
  attackOut: pose({ shoulder: [2, 30], elbow: [9, 28], hand: [16, 26], tip: [tipAt("attack"), 26] }),
  attackHold: pose({ shoulder: [2, 30], elbow: [9, 28], hand: [15, 26], tip: [tipAt("attack") - 2, 25], hip: [-1, 19] }),
  attackBack: pose({ elbow: [5, 26], hand: [12, 26], tip: [24, 29], hip: [-3, 18] }),

  // Lunge: rear leg locks straight, front foot lands long, blade and rear arm
  // counterbalance. The body drops ~4 units, which is most of the impact.
  //
  // The lunge is the one place either length is allowed to stretch, and it has
  // to be: `ACTIONS.lunge.reach` is 20 units beyond the attack's, while the
  // origin these coordinates hang off is the fencer's *centre*, which the
  // engine never moves. So the whole 20 has to come out of the drawing. The
  // torso leans over the front leg (neck and shoulder travel with it) and the
  // hand goes to 25 — that puts most of the extra range in the body committing
  // and leaves the rest, not all of it, in the steel.
  lungeWind: pose({
    hip: [-5, 16], neck: [-4, 28], head: [-3, 33], shoulder: [-2, 27],
    backKnee: [-10, 8], frontKnee: [6, 8], frontFoot: [10, 0],
    elbow: [1, 22], hand: [7, 23], tip: [19, 29], rearElbow: [-10, 30], rearHand: [-14, 34],
  }),
  lungeOut: pose({
    hip: [2, 15], neck: [4, 27], head: [6, 32],
    backKnee: [-11, 5], backFoot: [-18, 0],
    frontKnee: [17, 8], frontFoot: [27, 0],
    shoulder: [7, 26], elbow: [16, 24], hand: [25, 22], tip: [tipAt("lunge"), 21],
    rearElbow: [-6, 24], rearHand: [-14, 12],
  }),
  lungeRecover: pose({
    hip: [-1, 17], neck: [-2, 29], head: [-1, 34], shoulder: [0, 28],
    backKnee: [-10, 8], backFoot: [-15, 0],
    frontKnee: [12, 9], frontFoot: [19, 0],
    elbow: [8, 26], hand: [15, 25], tip: [31, 26], rearElbow: [-9, 30], rearHand: [-13, 35],
  }),

  // Parry: blade swept across the high line, hand strong, body upright.
  parry1: pose({ elbow: [4, 25], hand: [11, 26], tip: [19, 38] }),
  parry2: pose({ elbow: [5, 25], hand: [13, 26], tip: [22, 37], hip: [-1, 19] }),
  parryWhiff: pose({ elbow: [1, 22], hand: [7, 21], tip: [15, 32], hip: [-4, 18], neck: [-3, 30], shoulder: [-1, 29] }),

  // Jump back: both feet leave the piste, the whole figure lifts.
  jump1: pose({
    hip: [-3, 23], neck: [-2, 35], head: [-1, 40], shoulder: [1, 34],
    backKnee: [-9, 14], backFoot: [-13, 6], frontKnee: [5, 15], frontFoot: [8, 8],
    elbow: [1, 27], hand: [8, 29], tip: [20, 34], rearElbow: [-9, 36], rearHand: [-12, 42],
  }),
  jump2: pose({
    hip: [-3, 21], neck: [-2, 33], head: [-1, 38], shoulder: [1, 32],
    backKnee: [-10, 11], backFoot: [-16, 3], frontKnee: [4, 12], frontFoot: [4, 5],
    elbow: [1, 25], hand: [8, 27], tip: [20, 32], rearElbow: [-9, 34], rearHand: [-12, 40],
  }),
  jumpLand: pose({ hip: [-3, 17], neck: [-2, 29], head: [-1, 34], shoulder: [0, 28], backKnee: [-9, 8], frontKnee: [6, 8] }),

  // Recoil: parried, blade knocked off line, weight thrown back.
  recoil1: pose({
    hip: [-5, 18], neck: [-6, 30], head: [-7, 35], shoulder: [-4, 29],
    elbow: [-1, 24], hand: [4, 29], tip: [10, 41], rearElbow: [-11, 30], rearHand: [-15, 36],
  }),
  recoil2: pose({
    hip: [-4, 18], neck: [-5, 30], head: [-6, 35], shoulder: [-3, 29],
    elbow: [1, 24], hand: [7, 27], tip: [17, 35],
  }),
};

// action -> phase -> keyframes, played in order across that phase's duration.
const POSES = {
  garde: {
    idle: [P.garde, P.breathe],
    advance: [P.garde, P.advance1, P.garde, P.advance2],
    retreat: [P.garde, P.retreat1, P.garde, P.retreat2],
  },
  attack: {
    windup: [P.attackWind],
    active: [P.attackOut, P.attackHold],
    recovery: [P.attackBack, P.garde],
  },
  riposte: {
    windup: [P.attackWind],
    active: [P.attackOut, P.attackHold],
    recovery: [P.attackBack],
  },
  lunge: {
    windup: [P.lungeWind],
    active: [P.lungeOut],
    recovery: [P.lungeOut, P.lungeRecover, P.garde],
  },
  parry: {
    active: [P.parry1, P.parry2],
    recovery: [P.parryWhiff, P.parryWhiff, P.garde],
  },
  jumpback: {
    active: [P.jump1, P.jump2],
    recovery: [P.jumpLand, P.garde],
  },
  recoil: {
    recovery: [P.recoil1, P.recoil2, P.garde],
  },
};

const PHASE_ORDER = ["windup", "active", "recovery"];

/** The keyframe list for `f`'s current action and phase, and the index into it. */
function frameCursor(f) {
  const frames = POSES[f.action]?.[f.phase] ?? POSES[f.action]?.active ?? [P.garde];
  const total = phaseDuration(f) || ACTIONS[f.action]?.[f.phase] || 1;
  // Quantise to the 12fps grid first, then index — so a long phase holds each
  // keyframe for whole frames rather than easing through them.
  const stepped = Math.floor(f.t / FRAME_MS) * FRAME_MS;
  const i = Math.floor((stepped / total) * frames.length);
  return { frames, i: Math.min(frames.length - 1, Math.max(0, i)) };
}

/** The garde cycle frame for `f` at `time` — idle breath, advance or retreat. */
function gardeFrame(f, time) {
  const set = f.move > 0 ? "advance" : f.move < 0 ? "retreat" : "idle";
  const frames = POSES.garde[set];
  // Idle breathes at a third of the walk cadence; a 12fps breath is a twitch.
  const period = set === "idle" ? FRAME_MS * 4 : FRAME_MS;
  return frames[Math.floor(time / period) % frames.length];
}

/**
 * The pose to draw for `f` right now. `time` is the match clock in ms, used
 * only for the idle and walk cycles.
 */
export function poseFor(f, time) {
  if (f.action === "garde") return gardeFrame(f, time);
  const { frames, i } = frameCursor(f);
  return frames[i];
}

/**
 * The keyframe `f` was on one step ago — what the blade trail in `render.js`
 * interpolates back towards. On the first frame of a phase it reaches into the
 * phase before, falling back to en garde, because that is where every action
 * actually starts from.
 */
export function previousPose(f, time) {
  if (f.action === "garde") return gardeFrame(f, time);
  const { frames, i } = frameCursor(f);
  if (i > 0) return frames[i - 1];
  const earlier = POSES[f.action]?.[PHASE_ORDER[PHASE_ORDER.indexOf(f.phase) - 1]];
  return earlier ? earlier[earlier.length - 1] : P.garde;
}
