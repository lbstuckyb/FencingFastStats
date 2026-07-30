// Canvas drawing. Reads every colour from the site's CSS custom properties, so
// the salle follows the theme toggle exactly the way the charts do — the retro
// feel comes from the 320x180 internal resolution and the 12fps pose stepping
// in `poses.js`, not from a hard-coded palette.
//
// Nothing here decides anything: it draws whatever `engine.js` produced.

import { CONFIG } from "./engine.js";
import { FRAME_MS, poseFor } from "./poses.js";

export const WIDTH = 320;
export const HEIGHT = 180;

const GROUND = 150; // piste surface, in canvas y
const PISTE_H = 10;
// The top of the salle. The strip above it is the HUD's alone — see drawSalle.
const CEILING = 32;

const read = (styles, name, fallback) => styles.getPropertyValue(name).trim() || fallback;

/** Pulls the palette off `node`'s computed style. Call again on theme change. */
export function readPalette(node) {
  const styles = getComputedStyle(node || document.documentElement);
  const series = (i) => read(styles, `--series-${i}`, "#2a78d6");
  return {
    sky: read(styles, "--surface-0", "#f4f3f0"),
    wall: read(styles, "--surface-2", "#eceae5"),
    piste: read(styles, "--surface-1", "#fcfcfb"),
    line: read(styles, "--border", "#dedcd5"),
    lineStrong: read(styles, "--border-strong", "#c6c3b9"),
    text: read(styles, "--text-primary", "#0b0b0b"),
    muted: read(styles, "--text-muted", "#78766f"),
    series: [series(1), series(2), series(3), series(4), series(5), series(6)],
  };
}

function line(ctx, a, b, width, color) {
  ctx.beginPath();
  ctx.moveTo(a[0], a[1]);
  ctx.lineTo(b[0], b[1]);
  ctx.lineWidth = width;
  ctx.strokeStyle = color;
  ctx.stroke();
}

// ---- the salle -------------------------------------------------------------

function drawSalle(ctx, palette) {
  ctx.fillStyle = palette.sky;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);

  // Everything above CEILING belongs to the HUD. Scene furniture drawn up
  // there strikes straight through the score and the opponent's name.
  ctx.fillStyle = palette.wall;
  ctx.fillRect(0, CEILING, WIDTH, GROUND - CEILING);
  ctx.globalAlpha = 0.6;
  for (let x = 16; x < WIDTH; x += 32) line(ctx, [x, CEILING], [x, GROUND], 1, palette.line);
  line(ctx, [0, CEILING + 0.5], [WIDTH, CEILING + 0.5], 1, palette.lineStrong);
  line(ctx, [0, 100.5], [WIDTH, 100.5], 1, palette.line);
  ctx.globalAlpha = 1;

  // Lights hanging off the ceiling line, for a little depth.
  for (let x = 40; x < WIDTH; x += 80) {
    line(ctx, [x, CEILING], [x, CEILING + 6], 1, palette.line);
    ctx.fillStyle = palette.lineStrong;
    ctx.fillRect(x - 9, CEILING + 6, 18, 3);
  }
}

function drawPiste(ctx, palette, state) {
  const { left, right, centre } = CONFIG.piste;
  ctx.fillStyle = palette.piste;
  ctx.fillRect(left - 10, GROUND, right - left + 20, PISTE_H);
  line(ctx, [left - 10, GROUND + 0.5], [right + 10, GROUND + 0.5], 1, palette.lineStrong);
  line(ctx, [left - 10, GROUND + PISTE_H], [right + 10, GROUND + PISTE_H], 1, palette.line);

  // Centre line, then the two rear limits — each in its own fencer's colour and
  // brightening as that fencer runs out of piste, because crossing one is a
  // touch against them.
  ctx.setLineDash([3, 3]);
  line(ctx, [centre + 0.5, GROUND - 16], [centre + 0.5, GROUND + PISTE_H], 1, palette.line);
  ctx.setLineDash([]);

  // Each fencer's own back line, in their own colour, brightening as they run
  // out of piste — crossing it concedes a touch, so it has to be readable at a
  // glance. The warning hatching lies *inside* the piste band rather than up
  // beside the post: a fencer standing on their limit would otherwise cover
  // the one mark that is trying to warn them.
  const limits = [
    [left, playerColor(palette), 1, state.player.x - left],
    [right, opponentColor(palette, state), -1, right - state.opponent.x],
  ];
  for (const [x, color, inward, room] of limits) {
    ctx.globalAlpha = room < 30 ? 1 : 0.5;
    line(ctx, [x + 0.5, GROUND - 24], [x + 0.5, GROUND + PISTE_H], 1, color);
    for (let i = 0; i < 5; i += 1) {
      const hx = x + inward * i * 4;
      line(ctx, [hx, GROUND + PISTE_H], [hx + inward * 4, GROUND + 1], 1, color);
    }
    ctx.globalAlpha = 1;
  }
}

// ---- fencers ---------------------------------------------------------------

const playerColor = (palette) => palette.text;
const opponentColor = (palette, state) =>
  palette.series[(state.bout + 1) % palette.series.length];

function drawFencer(ctx, f, state, palette, body, blade) {
  const p = poseFor(f, state.time);
  const px = (j) => f.x + f.dir * j[0];
  const py = (j) => GROUND - j[1];
  const seg = (a, b, w) => line(ctx, [px(p[a]), py(p[a])], [px(p[b]), py(p[b])], w, body);

  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  // Rear arm first: it sits behind the torso in the silhouette.
  ctx.globalAlpha = 0.75;
  seg("neck", "rearElbow", 2.2);
  seg("rearElbow", "rearHand", 2.2);
  ctx.globalAlpha = 1;

  seg("hip", "backKnee", 2.6);
  seg("backKnee", "backFoot", 2.6);
  seg("hip", "frontKnee", 2.8);
  seg("frontKnee", "frontFoot", 2.8);
  seg("hip", "neck", 3.2);
  seg("shoulder", "elbow", 2.4);
  seg("elbow", "hand", 2.4);

  ctx.fillStyle = body;
  ctx.beginPath();
  ctx.arc(px(p.head), py(p.head), 3.4, 0, Math.PI * 2);
  ctx.fill();

  // Bell guard and blade. The blade is the only 1px mark on screen, which is
  // what makes an extension read at a glance.
  ctx.beginPath();
  ctx.arc(px(p.hand), py(p.hand), 1.9, 0, Math.PI * 2);
  ctx.fillStyle = blade;
  ctx.fill();
  line(ctx, [px(p.hand), py(p.hand)], [px(p.tip), py(p.tip)], 1, blade);

  // Riposte window: a bar over the head, the only thing on the piste that
  // blinks, because it is the only thing that expires.
  if (f.riposte > 0) {
    const on = Math.floor(state.time / FRAME_MS) % 2 === 0;
    if (on) {
      ctx.fillStyle = blade;
      ctx.fillRect(px(p.head) - 5, py(p.head) - 9, 10, 2);
    }
  }
  ctx.lineCap = "butt";
}

// ---- hud -------------------------------------------------------------------

function drawHud(ctx, state, palette) {
  ctx.font = "bold 10px system-ui, -apple-system, sans-serif";
  ctx.textBaseline = "top";

  // Lives as blade pips: filled while you still have them, hollow once spent.
  for (let i = 0; i < CONFIG.lives; i += 1) {
    const x = 10 + i * 9;
    const spent = i >= state.lives;
    ctx.globalAlpha = spent ? 0.35 : 1;
    ctx.strokeStyle = palette.text;
    ctx.fillStyle = palette.text;
    ctx.lineWidth = 1;
    if (spent) ctx.strokeRect(x + 0.5, 8.5, 4, 9);
    else ctx.fillRect(x, 8, 5, 10);
    ctx.globalAlpha = 1;
  }

  ctx.fillStyle = palette.text;
  ctx.textAlign = "right";
  ctx.fillText(String(state.score).padStart(3, "0"), WIDTH - 10, 9);
  ctx.textAlign = "left";
  ctx.fillStyle = palette.muted;
  ctx.font = "9px system-ui, -apple-system, sans-serif";
  ctx.fillText("TOUCHES", WIDTH - 10 - ctx.measureText("TOUCHES").width, 21);

  ctx.textAlign = "center";
  ctx.fillText(state.opponentName.toUpperCase(), WIDTH / 2, 9);
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

// ---- the frame -------------------------------------------------------------

/**
 * Draws one frame. `opts.reducedMotion` drops the shake and the touch flash,
 * which are the only two effects that move the whole screen.
 */
export function draw(ctx, state, palette, opts = {}) {
  const shake = opts.reducedMotion ? 0 : state.shake;
  // Stepped, not smooth: the shake is on the same 12fps grid as everything else.
  const offset = shake > 0 ? (Math.floor(state.time / FRAME_MS) % 2 ? 1 : -1) * Math.ceil(shake / 60) : 0;

  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, WIDTH, HEIGHT);
  ctx.translate(offset, 0);

  drawSalle(ctx, palette);
  drawPiste(ctx, palette, state);
  drawFencer(ctx, state.opponent, state, palette, opponentColor(palette, state), opponentColor(palette, state));
  drawFencer(ctx, state.player, state, palette, playerColor(palette), palette.series[0]);
  drawHud(ctx, state, palette);

  if (!opts.reducedMotion && state.flash > 0) {
    ctx.globalAlpha = Math.min(0.5, state.flash / 480);
    ctx.fillStyle = palette.piste;
    ctx.fillRect(-4, 0, WIDTH + 8, HEIGHT);
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}
