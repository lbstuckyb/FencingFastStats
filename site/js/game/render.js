// Canvas drawing. Reads every colour from the site's CSS custom properties, so
// the salle follows the theme toggle exactly the way the charts do, and nothing
// here is hard-coded to a theme.
//
// 320x180 is a *coordinate space*, not a resolution: `draw()` scales the whole
// context by however much bigger the backing store is, so the marks are vector
// line art rendered at device resolution while every number below stays in the
// small, readable space. The weight in the animation comes from the 12fps pose
// stepping in `poses.js` — nothing here depends on a pixel grid.
//
// Nothing here decides anything: it draws whatever `engine.js` produced.

import { BLADE_ACTIONS, CONFIG } from "./engine.js";
import { FRAME_MS, GARDE_HIP, poseFor, previousPose } from "./poses.js";

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
  const series = (i) => read(styles, `--series-${i}`, "#1233e0");
  return {
    sky: read(styles, "--surface-0", "#ffffff"),
    wall: read(styles, "--surface-2", "#eceef1"),
    piste: read(styles, "--surface-1", "#ffffff"),
    line: read(styles, "--border", "#c9ccd2"),
    lineStrong: read(styles, "--border-strong", "#000000"),
    text: read(styles, "--text-primary", "#000000"),
    muted: read(styles, "--text-muted", "#6b7078"),
    series: [series(1), series(2), series(3), series(4), series(5), series(6)],
  };
}

const lerp = (a, b, t) => a + (b - a) * t;

function line(ctx, a, b, width, color) {
  ctx.beginPath();
  ctx.moveTo(a[0], a[1]);
  ctx.lineTo(b[0], b[1]);
  ctx.lineWidth = width;
  ctx.strokeStyle = color;
  ctx.stroke();
}

function ellipse(ctx, x, y, rx, ry, color) {
  ctx.beginPath();
  ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

// ---- the salle -------------------------------------------------------------

function drawSalle(ctx, palette) {
  ctx.fillStyle = palette.sky;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);

  // Everything above CEILING belongs to the HUD. Scene furniture drawn up
  // there strikes straight through the score and the opponent's name.
  // The wall graduates sky -> wall from the ceiling down, which is all the
  // depth a flat side view needs to stop reading as a swatch.
  const wash = ctx.createLinearGradient(0, CEILING, 0, GROUND);
  wash.addColorStop(0, palette.sky);
  wash.addColorStop(1, palette.wall);
  ctx.fillStyle = wash;
  ctx.fillRect(0, CEILING, WIDTH, GROUND - CEILING);

  ctx.globalAlpha = 0.6;
  for (let x = 16; x < WIDTH; x += 32) line(ctx, [x, CEILING], [x, GROUND], 1, palette.line);
  line(ctx, [0, CEILING + 0.5], [WIDTH, CEILING + 0.5], 1, palette.lineStrong);
  line(ctx, [0, 100.5], [WIDTH, 100.5], 1, palette.line);
  ctx.globalAlpha = 1;

  // A row of spectators, far enough back to be dots. Low alpha on purpose:
  // this is the only mark in the salle carrying no gameplay signal, so it has
  // to stay under the notice threshold.
  ctx.globalAlpha = 0.15;
  for (let x = 12; x < WIDTH; x += 9) {
    ellipse(ctx, x, 64 + (x % 18 === 3 ? 1.5 : 0), 2, 2.4, palette.lineStrong);
  }
  ctx.globalAlpha = 1;

  // Lights hanging off the ceiling line, for a little depth.
  for (let x = 40; x < WIDTH; x += 80) {
    line(ctx, [x, CEILING], [x, CEILING + 6], 1, palette.line);
    ctx.fillStyle = palette.lineStrong;
    ctx.fillRect(x - 9, CEILING + 6, 18, 3);
  }
}

// The scoring apparatus: one lamp per fencer, on that fencer's own side, the
// way a real box is wired. It hangs between the HUD strip and the spectators,
// well clear of anything a lunge can reach.
function drawApparatus(ctx, state, palette) {
  const w = 46;
  const h = 18;
  const x = WIDTH / 2 - w / 2;
  const y = 36;

  line(ctx, [WIDTH / 2, CEILING + 1], [WIDTH / 2, y], 1, palette.lineStrong);
  ctx.fillStyle = palette.piste;
  ctx.fillRect(x, y, w, h);
  ctx.lineWidth = 1;
  ctx.strokeStyle = palette.lineStrong;
  ctx.strokeRect(x, y, w, h);

  const lit = state.flash > 0 ? state.lamp : null;
  const lamps = [
    [x + 12, playerColor(palette), lit === "player" || lit === "both"],
    [x + w - 12, opponentColor(palette, state), lit === "opponent" || lit === "both"],
  ];
  for (const [lx, color, on] of lamps) {
    ctx.globalAlpha = on ? 1 : 0.25;
    ellipse(ctx, lx, y + h / 2, 6.5, 5, on ? color : palette.lineStrong);
    ctx.globalAlpha = 1;
    ctx.beginPath();
    ctx.ellipse(lx, y + h / 2, 6.5, 5, 0, 0, Math.PI * 2);
    ctx.lineWidth = 0.8;
    ctx.strokeStyle = palette.lineStrong;
    ctx.stroke();
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

  // A sheen off the floor immediately below the piste, so the strip reads as
  // sitting on something rather than floating on the background.
  const sheen = ctx.createLinearGradient(0, GROUND + PISTE_H, 0, GROUND + PISTE_H + 10);
  sheen.addColorStop(0, palette.wall);
  sheen.addColorStop(1, palette.sky);
  ctx.globalAlpha = 0.55;
  ctx.fillStyle = sheen;
  ctx.fillRect(0, GROUND + PISTE_H, WIDTH, 10);
  ctx.globalAlpha = 1;
}

// ---- fencers ---------------------------------------------------------------

const playerColor = (palette) => palette.text;
const opponentColor = (palette, state) =>
  palette.series[(state.bout + 1) % palette.series.length];

// A contact shadow, so the figure stands on the piste instead of hovering over
// it. It spreads with the feet — widest and darkest at the bottom of a lunge —
// and fades out as the hip lifts above its garde height, which is the whole
// tell that a jump-back has left the floor.
function drawShadow(ctx, f, state, palette) {
  const p = poseFor(f, state.time);
  const lift = Math.max(0, p.hip[1] - GARDE_HIP);
  const alpha = 0.24 * Math.max(0, 1 - lift / 5);
  if (alpha <= 0.01) return;
  const spread = Math.abs(p.frontFoot[0] - p.backFoot[0]);
  const centre = f.x + (f.dir * (p.frontFoot[0] + p.backFoot[0])) / 2;
  ctx.globalAlpha = alpha;
  ellipse(ctx, centre, GROUND + 2, spread * 0.5 + 3, 2, palette.lineStrong);
  ctx.globalAlpha = 1;
}

// Blade, drawn tapered off the bell guard: a heavier forte, a thin foible and a
// dot for the point. Thin on purpose — a blade as wide as a limb stops reading
// as steel. `ghost` drops the point, so the trail behind an extension reads as
// one blade smearing rather than three blades.
function bladeMark(ctx, hand, tip, color, alpha = 1, ghost = false) {
  const mid = [lerp(hand[0], tip[0], 0.4), lerp(hand[1], tip[1], 0.4)];
  ctx.globalAlpha = alpha;
  line(ctx, hand, mid, 1.0, color);
  line(ctx, mid, tip, 0.5, color);
  if (!ghost) ellipse(ctx, tip[0], tip[1], 0.7, 0.7, color);
  ctx.globalAlpha = 1;
}

function drawFencer(ctx, f, state, palette, body, blade, opts = {}) {
  const p = poseFor(f, state.time);
  const px = (j) => f.x + f.dir * j[0];
  const py = (j) => GROUND - j[1];
  const at = (j) => [px(j), py(j)];
  const seg = (a, b, w) => line(ctx, at(p[a]), at(p[b]), w, body);

  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  // Rear arm first: it sits behind the torso in the silhouette.
  ctx.globalAlpha = 0.75;
  seg("neck", "rearElbow", 2.2);
  seg("rearElbow", "rearHand", 2.2);
  ctx.globalAlpha = 1;

  // Legs taper: the thigh carries the weight, the shin only carries the foot.
  seg("hip", "backKnee", 3.0);
  seg("backKnee", "backFoot", 2.2);
  seg("hip", "frontKnee", 3.2);
  seg("frontKnee", "frontFoot", 2.4);

  // Jacket, not a spine: a quad wider at the chest than at the waist. This is
  // the single mark that turns the figure from a stick into a fencer.
  const hip = at(p.hip);
  const neck = at(p.neck);
  const dx = neck[0] - hip[0];
  const dy = neck[1] - hip[1];
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const flank = (point, w, sign) => [point[0] + sign * nx * w, point[1] + sign * ny * w];
  ctx.beginPath();
  ctx.moveTo(...flank(hip, 2.2, 1));
  ctx.lineTo(...flank(neck, 3.6, 1));
  ctx.lineTo(...flank(neck, 3.6, -1));
  ctx.lineTo(...flank(hip, 2.2, -1));
  ctx.closePath();
  ctx.fillStyle = body;
  ctx.fill();
  ctx.lineWidth = 1;
  ctx.strokeStyle = body;
  ctx.stroke();

  seg("shoulder", "elbow", 2.4);
  seg("elbow", "hand", 2.4);

  // The mask: a dome with a bib flaring down toward the collar, and two mesh
  // strokes across the front. Both are oriented by `f.dir`, so which way a
  // fencer is facing is legible from the head alone.
  const head = at(p.head);
  const d = f.dir;
  ctx.fillStyle = body;
  ctx.beginPath();
  ctx.moveTo(head[0] - d * 3.4, head[1] + 1.2);
  ctx.lineTo(head[0] + d * 3.6, head[1] + 0.4);
  ctx.lineTo(head[0] + d * 2.6, head[1] + 5.4);
  ctx.lineTo(neck[0] - d * 1.6, neck[1] + 0.4);
  ctx.closePath();
  ctx.fill();
  ellipse(ctx, head[0], head[1], 3.6, 4.2, body);
  ctx.globalAlpha = 0.4;
  line(ctx, [head[0] + d * 0.4, head[1] - 2.4], [head[0] + d * 3.2, head[1] - 1.0], 0.7, palette.sky);
  line(ctx, [head[0] + d * 0.2, head[1] + 0.4], [head[0] + d * 3.4, head[1] + 1.2], 0.7, palette.sky);
  ctx.globalAlpha = 1;

  // Blade trail: two ghosts strung back toward where the blade was one
  // keyframe ago. On a 12fps step the eye has no in-betweens to work with, so
  // this is what turns an extension into a movement rather than a jump cut.
  const sweeping =
    BLADE_ACTIONS.has(f.action) || (f.action === "parry" && f.phase === "active");
  if (!opts.reducedMotion && sweeping && f.phase === "active") {
    const q = previousPose(f, state.time);
    const back = (from, to, t) => [lerp(px(from), px(to), t), lerp(py(from), py(to), t)];
    for (const [t, alpha] of [[0.66, 0.3], [0.33, 0.15]]) {
      bladeMark(ctx, back(q.hand, p.hand, t), back(q.tip, p.tip, t), blade, alpha, true);
    }
  }

  ellipse(ctx, px(p.hand), py(p.hand), 1.9, 1.9, blade);
  bladeMark(ctx, at(p.hand), at(p.tip), blade);

  // Riposte window: a bar over the head, the only thing on the piste that
  // blinks, because it is the only thing that expires.
  if (f.riposte > 0) {
    const on = Math.floor(state.time / FRAME_MS) % 2 === 0;
    if (on) {
      ctx.fillStyle = blade;
      ctx.fillRect(head[0] - 5, head[1] - 9, 10, 2);
    }
  }
  ctx.lineCap = "butt";
}

// ---- hud -------------------------------------------------------------------

function drawHud(ctx, state, palette) {
  ctx.font = "bold 10px Archivo, system-ui, sans-serif";
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
  ctx.font = "9px Archivo, system-ui, sans-serif";
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

  // Everything below is written in the 320x180 space; this is the one line
  // that maps it onto however many device pixels the layout actually gave us,
  // so the line art is resolution-independent rather than an upscaled buffer.
  const k = ctx.canvas.width / WIDTH || 1;

  ctx.save();
  ctx.setTransform(k, 0, 0, k, 0, 0);
  ctx.clearRect(0, 0, WIDTH, HEIGHT);
  ctx.translate(offset, 0);

  drawSalle(ctx, palette);
  drawApparatus(ctx, state, palette);
  drawPiste(ctx, palette, state);
  drawShadow(ctx, state.opponent, state, palette);
  drawShadow(ctx, state.player, state, palette);
  const oppColor = opponentColor(palette, state);
  drawFencer(ctx, state.opponent, state, palette, oppColor, oppColor, opts);
  drawFencer(ctx, state.player, state, palette, playerColor(palette), palette.series[0], opts);
  drawHud(ctx, state, palette);

  if (!opts.reducedMotion && state.flash > 0) {
    ctx.globalAlpha = Math.min(0.5, state.flash / 480);
    ctx.fillStyle = palette.piste;
    ctx.fillRect(-4, 0, WIDTH + 8, HEIGHT);
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}
