// Fencer search: fully client-side over data/fencers/index.json (~1 MB,
// 17k entries). Only fencers with >=2 competitions are in the index, so every
// result is guaranteed to have a profile shard behind it.

import { POOLS, getFencerIndex, weaponName } from "../data.js";
import { el, fencerHref, fmtInt, normalize } from "../util.js";

const MAX_RESULTS = 100;

// Index entries: {i: id, n: name, c: country, w: weapons ("EF"), g: gender}
let prepared = null;
async function preparedIndex() {
  if (!prepared) {
    const raw = await getFencerIndex();
    prepared = raw.map((e) => ({ ...e, n: (e.n ?? "").trim(), key: normalize(e.n) }));
  }
  return prepared;
}

function matches(entry, terms, pool) {
  if (pool && !(entry.w?.includes(pool.weapon) && entry.g === pool.gender)) return false;
  return terms.every((t) => entry.key.includes(t));
}

function score(entry, terms) {
  // Prefix hits first (typing "kano" should surface KANO before HIKANO), then
  // shorter names, then alphabetical — the sort is stable on an A-Z index.
  const first = terms[0];
  if (entry.key.startsWith(first)) return 0;
  if (entry.key.includes(` ${first}`)) return 1;
  return 2;
}

function resultRow(entry) {
  return el("li", {}, [
    el("a", { href: fencerHref(entry.i) }, [
      el("span", { class: "name", text: entry.n || `#${entry.i}` }),
      el("span", { class: "flag", text: entry.c ?? "—" }),
      el("span", { class: "small muted", text: [...(entry.w ?? "")].map(weaponName).join(" · ") }),
    ]),
  ]);
}

export async function render({ params }) {
  const index = await preparedIndex();

  const initialQuery = params.get("q") ?? "";
  const initialPool = params.get("pool") ?? "";

  const input = el("input", {
    class: "search-box",
    type: "search",
    id: "fencer-search",
    placeholder: "Search 17,000 fencers by name — e.g. Szilagyi, Kano, Kharlan",
    autocomplete: "off",
    value: initialQuery,
  });
  const status = el("p", { class: "small muted", "aria-live": "polite" });
  const list = el("ul", { class: "result-list" });

  const filter = el(
    "div",
    { class: "pool-filter", role: "group", "aria-label": "Filter by weapon and gender" },
    [
      el("button", { type: "button", text: "All", "data-pool": "", "aria-pressed": initialPool ? "false" : "true" }),
      ...POOLS.map((p) =>
        el("button", {
          type: "button",
          text: p.label,
          "data-pool": p.code,
          "aria-pressed": p.code === initialPool ? "true" : "false",
        })
      ),
    ]
  );

  let poolCode = initialPool;

  function run() {
    const query = input.value.trim();
    const terms = normalize(query).split(/\s+/).filter(Boolean);
    const pool = POOLS.find((p) => p.code === poolCode) ?? null;

    if (!terms.length && !pool) {
      list.replaceChildren();
      status.textContent = `${fmtInt(index.length)} fencers indexed. Start typing a name, or pick a weapon.`;
      return;
    }

    const hits = index.filter((e) => matches(e, terms, pool));
    if (terms.length) {
      hits.sort((a, b) => score(a, terms) - score(b, terms) || a.n.length - b.n.length);
    }

    list.replaceChildren(...hits.slice(0, MAX_RESULTS).map(resultRow));
    status.textContent = hits.length === 0
      ? "No fencer matches that search."
      : hits.length > MAX_RESULTS
        ? `${fmtInt(hits.length)} matches — showing the first ${MAX_RESULTS}. Keep typing to narrow it down.`
        : `${fmtInt(hits.length)} ${hits.length === 1 ? "match" : "matches"}.`;
  }

  // The whole index is in memory, so filtering is a few ms — no debounce needed.
  input.addEventListener("input", run);
  filter.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    poolCode = button.dataset.pool;
    for (const b of filter.querySelectorAll("button")) {
      b.setAttribute("aria-pressed", b === button ? "true" : "false");
    }
    run();
  });

  run();
  // Autofocus only helps on a pointer/keyboard device; harmless elsewhere.
  requestAnimationFrame(() => input.focus());

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Find a fencer" }),
      el("p", { class: "muted", text: "Everyone with at least two competitions on the international circuit." }),
    ]),
    el("div", { class: "card" }, [
      el("label", { class: "small muted", for: "fencer-search", text: "Fencer name" }),
      input,
      filter,
      status,
      list,
    ]),
  ]);
}
