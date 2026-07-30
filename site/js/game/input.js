// Keyboard and on-screen buttons, folded into the one flag object the engine
// consumes. The engine never sees an event.
//
// Two things this has to get right or it breaks the rest of the page: it must
// not swallow keys aimed at a link, a button or a field (the nav and the theme
// toggle both live on space/enter), and it must `preventDefault` only its own
// keys, so the page still scrolls normally when the game isn't listening.

// Held movement plus the one-shot blade actions. `a`/`d`/`f` are the fencing
// keys; the arrows move. Space is the jump because it is the panic button.
const KEYMAP = {
  ArrowLeft: { hold: "left" },
  ArrowRight: { hold: "right" },
  a: { action: "attack" },
  d: { action: "parry" },
  f: { action: "lunge" },
  " ": { action: "jump" },
};

export const CONTROLS = [
  { key: "ArrowLeft", label: "◀", name: "Retreat" },
  { key: "ArrowRight", label: "▶", name: "Advance" },
  { key: "a", label: "A", name: "Attack" },
  { key: "d", label: "D", name: "Parry" },
  { key: "f", label: "F", name: "Lunge" },
  { key: " ", label: "⤺", name: "Jump back" },
];

// A focused nav link or the theme toggle must keep space and enter for itself.
// The game's own buttons are the exception: pressing "Attack" with a finger and
// then "F" on the keyboard has to keep working, and after a tap they hold focus.
function ownsKeys(node, root) {
  if (!node || node === document.body) return false;
  if (node.isContentEditable) return true;
  if (["INPUT", "TEXTAREA", "SELECT", "SUMMARY"].includes(node.tagName)) return true;
  if (["BUTTON", "A"].includes(node.tagName)) return !root.contains(node);
  return false;
}

/**
 * Wires `node`'s `[data-game-key]` buttons and the window keyboard onto one
 * input object. `isLive()` says whether a run is currently accepting keys —
 * when it is false nothing is captured and no default is prevented.
 *
 * Returns `{ input, detach }`. `input.take()` pops the queued one-shot action.
 */
export function attach(node, isLive = () => true) {
  const held = new Set();
  let queued = null;

  const input = {
    get left() { return held.has("left"); },
    get right() { return held.has("right"); },
    take() { const a = queued; queued = null; return a; },
    clear() { held.clear(); queued = null; },
  };

  const press = (key) => {
    const map = KEYMAP[key];
    if (!map) return false;
    if (map.hold) held.add(map.hold);
    else queued = map.action;
    return true;
  };
  const release = (key) => {
    const map = KEYMAP[key];
    if (map && map.hold) held.delete(map.hold);
  };

  const onKeyDown = (ev) => {
    if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (ownsKeys(document.activeElement, node)) return;
    if (!isLive()) return;
    if (!KEYMAP[ev.key]) return;
    // Only now: the key is ours, a run is live, and nothing else wants it.
    ev.preventDefault();
    if (!ev.repeat) press(ev.key);
  };
  const onKeyUp = (ev) => release(ev.key);
  // A tab switch or an alt-tab never delivers the keyup, which would otherwise
  // leave a fencer walking into their own rear limit forever.
  const onBlur = () => input.clear();

  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);
  window.addEventListener("blur", onBlur);

  // Touch buttons. Pointer events cover mouse, pen and finger in one path;
  // `touch-action: none` in the CSS is what stops a press scrolling the page.
  const buttons = [...node.querySelectorAll("[data-game-key]")];
  const bound = [];
  for (const button of buttons) {
    const key = button.dataset.gameKey;
    const down = (ev) => {
      ev.preventDefault();
      button.setPointerCapture?.(ev.pointerId);
      press(key);
    };
    const up = () => release(key);
    button.addEventListener("pointerdown", down);
    button.addEventListener("pointerup", up);
    button.addEventListener("pointercancel", up);
    button.addEventListener("pointerleave", up);
    bound.push([button, down, up]);
  }

  const detach = () => {
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("keyup", onKeyUp);
    window.removeEventListener("blur", onBlur);
    for (const [button, down, up] of bound) {
      button.removeEventListener("pointerdown", down);
      button.removeEventListener("pointerup", up);
      button.removeEventListener("pointercancel", up);
      button.removeEventListener("pointerleave", up);
    }
    input.clear();
  };

  return { input, detach };
}
