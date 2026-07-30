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

import { ACTIONS, phaseDuration } from "./engine.js";

// The 12fps cadence the animation quantises to. Everything visible steps on
// this grid even though the frame loop runs at whatever the display gives us.
export const FRAME_MS = 1000 / 12;

const GARDE = {
  head: [0, 36],
  neck: [-1, 31],
  hip: [-2, 19],
  backKnee: [-8, 10],
  backFoot: [-11, 0],
  frontKnee: [7, 10],
  frontFoot: [11, 0],
  shoulder: [1, 30],
  elbow: [7, 26],
  hand: [13, 24],
  tip: [30, 26],
  rearElbow: [-8, 32],
  rearHand: [-11, 38],
};

// Poses are written as deltas from en garde so a keyframe only says what it
// changes — which is also how they stay readable as a table.
const pose = (overrides) => ({ ...GARDE, ...overrides });

const P = {
  garde: GARDE,
  // Idle isn't static: a 2-frame breath keeps a stopped fencer alive.
  breathe: pose({ head: [0, 35], neck: [-1, 30], hand: [13, 23], tip: [30, 25] }),

  advance1: pose({ frontKnee: [9, 12], frontFoot: [14, 3], hip: [-1, 20] }),
  advance2: pose({ backKnee: [-6, 10], backFoot: [-8, 2], hip: [0, 19] }),
  retreat1: pose({ backKnee: [-10, 12], backFoot: [-15, 3], hip: [-4, 20] }),
  retreat2: pose({ frontKnee: [5, 10], frontFoot: [8, 2], hip: [-3, 19] }),

  // Attack: the hand pulls back a hair, then the arm goes out first — épée's
  // whole point is that the hand leads.
  attackWind: pose({ hand: [10, 26], elbow: [4, 27], tip: [24, 30], hip: [-3, 19] }),
  attackOut: pose({ shoulder: [2, 30], elbow: [10, 25], hand: [18, 25], tip: [34, 25] }),
  attackHold: pose({ elbow: [9, 25], hand: [17, 25], tip: [33, 24], hip: [-1, 19] }),
  attackBack: pose({ elbow: [6, 26], hand: [12, 25], tip: [27, 27], hip: [-3, 18] }),

  // Lunge: rear leg locks straight, front foot lands long, blade and rear arm
  // counterbalance. The body drops ~4 units, which is most of the impact.
  lungeWind: pose({
    hip: [-5, 16], neck: [-4, 28], head: [-3, 33],
    backKnee: [-10, 8], frontKnee: [6, 8], frontFoot: [10, 0],
    elbow: [5, 24], hand: [11, 23], tip: [26, 24], rearElbow: [-10, 30], rearHand: [-14, 34],
  }),
  lungeOut: pose({
    hip: [2, 15], neck: [1, 27], head: [2, 32],
    backKnee: [-11, 5], backFoot: [-18, 0],
    frontKnee: [17, 8], frontFoot: [27, 0],
    shoulder: [4, 26], elbow: [13, 22], hand: [24, 21], tip: [58, 21],
    rearElbow: [-6, 24], rearHand: [-14, 12],
  }),
  lungeRecover: pose({
    hip: [-1, 17], neck: [-2, 29], head: [-1, 34],
    backKnee: [-10, 8], backFoot: [-15, 0],
    frontKnee: [12, 9], frontFoot: [19, 0],
    elbow: [9, 24], hand: [16, 23], tip: [34, 24], rearElbow: [-9, 30], rearHand: [-13, 35],
  }),

  // Parry: blade swept across the high line, hand strong, body upright.
  parry1: pose({ elbow: [8, 27], hand: [14, 27], tip: [22, 40] }),
  parry2: pose({ elbow: [9, 26], hand: [16, 26], tip: [26, 38], hip: [-1, 19] }),
  parryWhiff: pose({ elbow: [4, 24], hand: [9, 21], tip: [18, 10], hip: [-4, 18], neck: [-3, 30] }),

  // Jump back: both feet leave the piste, the whole figure lifts.
  jump1: pose({
    hip: [-3, 23], neck: [-2, 35], head: [-1, 40],
    backKnee: [-9, 14], backFoot: [-13, 6], frontKnee: [5, 15], frontFoot: [8, 8],
    elbow: [6, 29], hand: [12, 28], tip: [28, 31], rearElbow: [-9, 36], rearHand: [-12, 42],
  }),
  jump2: pose({
    hip: [-3, 21], neck: [-2, 33], head: [-1, 38],
    backKnee: [-10, 11], backFoot: [-16, 3], frontKnee: [4, 12], frontFoot: [4, 5],
    elbow: [6, 28], hand: [12, 27], tip: [28, 30], rearElbow: [-9, 34], rearHand: [-12, 40],
  }),
  jumpLand: pose({ hip: [-3, 17], neck: [-2, 29], head: [-1, 34], backKnee: [-9, 8], frontKnee: [6, 8] }),

  // Recoil: parried, blade knocked off line, weight thrown back.
  recoil1: pose({
    hip: [-5, 18], neck: [-6, 30], head: [-7, 35],
    elbow: [2, 27], hand: [6, 30], tip: [14, 44], rearElbow: [-11, 30], rearHand: [-15, 36],
  }),
  recoil2: pose({
    hip: [-4, 18], neck: [-5, 30], head: [-6, 35],
    elbow: [4, 26], hand: [9, 27], tip: [22, 36],
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

/**
 * The pose to draw for `f` right now. `time` is the match clock in ms, used
 * only for the idle and walk cycles.
 */
export function poseFor(f, time) {
  if (f.action === "garde") {
    const set = f.move > 0 ? "advance" : f.move < 0 ? "retreat" : "idle";
    const frames = POSES.garde[set];
    // Idle breathes at a third of the walk cadence; a 12fps breath is a twitch.
    const period = set === "idle" ? FRAME_MS * 4 : FRAME_MS;
    return frames[Math.floor(time / period) % frames.length];
  }
  const frames = POSES[f.action]?.[f.phase] ?? POSES[f.action]?.active ?? [P.garde];
  const total = phaseDuration(f) || ACTIONS[f.action]?.[f.phase] || 1;
  // Quantise to the 12fps grid first, then index — so a long phase holds each
  // keyframe for whole frames rather than easing through them.
  const stepped = Math.floor(f.t / FRAME_MS) * FRAME_MS;
  const i = Math.floor((stepped / total) * frames.length);
  return frames[Math.min(frames.length - 1, Math.max(0, i))];
}
