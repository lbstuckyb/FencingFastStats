// Type-ahead fencer picker over `fencers/index.json`, shared by head-to-head,
// the compare page and the profile's "compare with" control.

import { getFencerIndex } from "./data.js";
import { el, normalize } from "./util.js";

const SUGGESTIONS = 8;

let searchable = null;

/** The search index with a folded key per entry, parsed once per page load. */
export async function fencerSearchIndex() {
  if (!searchable) {
    searchable = getFencerIndex()
      .then((raw) => raw.map((e) => ({ ...e, key: normalize(e.n) })))
      .catch((err) => { searchable = null; throw err; });
  }
  return searchable;
}

/**
 * A labelled search box that suggests fencers as you type and calls
 * `onPick(id)` on selection. `index` is the array from `fencerSearchIndex()`.
 */
export function fencerPicker({ label, id, index, value = "", placeholder = "Type a fencer's name", onPick }) {
  const input = el("input", {
    class: "search-box", type: "search", id,
    placeholder, autocomplete: "off", value,
  });
  const list = el("ul", { class: "suggest" });

  const close = () => list.replaceChildren();

  input.addEventListener("input", () => {
    const terms = normalize(input.value).split(/\s+/).filter(Boolean);
    if (!terms.length) return close();
    const hits = index.filter((e) => terms.every((t) => e.key.includes(t))).slice(0, SUGGESTIONS);
    list.replaceChildren(...hits.map((e) =>
      el("li", {}, [
        el("button", { type: "button", "data-id": e.i }, [
          el("span", { class: "name", text: e.n }),
          el("span", { class: "flag", text: e.c ?? "" }),
        ]),
      ])
    ));
  });
  // The blur has to lose the race against the suggestion's own click.
  input.addEventListener("blur", () => setTimeout(close, 150));
  list.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    close();
    onPick(Number(button.dataset.id));
  });

  return el("div", { class: "h2h-picker" }, [
    label ? el("label", { class: "small muted", for: id, text: label }) : null,
    input,
    list,
  ]);
}
