// Metrics explorer: every competition metric for every fencer of one pool,
// aggregated over whatever season range and competition levels the reader
// picks, sortable on any column.
//
// Source data is `data/explore/{pool}.json` — one row per (athlete, season,
// level group) holding *sums* plus the population counts each mean has to be
// divided by. Aggregating client-side (rather than shipping pre-computed
// means) is what makes any filter combination come out right; see
// `src/ffs/build_site.py:build_explore`.

import {
  DEFAULT_POOL, POOLS, getExplore, getFencerIndex, getMeta, isPool, poolCodeOf,
} from "../data.js";
import { el, fencerHref, fmtInt, normalize } from "../util.js";
import {
  addRow, countIndexOf, emptyTotals, formatMetric, initialDirection, metricValue,
  ROW_ATHLETE, ROW_LEVEL_GROUP, ROW_SEASON,
} from "../metrics.js";

// The table is a scan-and-compare tool, not a directory: past a couple of
// hundred rows the reader is filtering, not scrolling.
const MAX_ROWS = 200;
const DEFAULT_MIN_COMPS = 5;

// Fixed columns, left of the metrics. `key` doubles as a sort key.
const FIXED_COLUMNS = [
  { key: "name", label: "Fencer", dir: 1 },
  { key: "country", label: "Country", dir: 1 },
  { key: "comps", label: "Comps", dir: -1, num: true },
];

// ---- data ------------------------------------------------------------------

// One entry per pool, kept for the life of the page: re-filtering must never
// re-parse a 4 MB file.
const poolCache = new Map();

async function loadPool(pool) {
  if (!poolCache.has(pool)) {
    poolCache.set(pool, (async () => {
      const [file, index] = await Promise.all([getExplore(pool), getFencerIndex()]);
      const people = new Map();
      for (const f of index) {
        if (poolCodeOf(f.w, f.g) === pool) {
          people.set(f.i, { name: f.n ?? `#${f.i}`, country: f.c ?? "", key: normalize(f.n ?? "") });
        }
      }
      const seasons = [...new Set(file.rows.map((r) => r[ROW_SEASON]))].sort();
      const countries = [...new Set([...people.values()].map((p) => p.country).filter(Boolean))].sort();
      return { file, people, seasons, countries };
    })().catch((err) => { poolCache.delete(pool); throw err; }));
  }
  return poolCache.get(pool);
}

/** Sum every row the filters select, per athlete, then divide once. */
function aggregate(data, meta, state) {
  const { file, people } = data;
  const countIndex = countIndexOf(meta);
  const nCounts = file.counts.length;
  const nMetrics = file.metrics.length;
  const levelWanted = file.level_groups.map((code) => state.levels.has(code));
  const terms = normalize(state.query).split(/\s+/).filter(Boolean);

  const totalsById = new Map();
  for (const row of file.rows) {
    const season = row[ROW_SEASON];
    if (season < state.from || season > state.to) continue;
    if (!levelWanted[row[ROW_LEVEL_GROUP]]) continue;
    const id = row[ROW_ATHLETE];
    let totals = totalsById.get(id);
    if (!totals) {
      const person = people.get(id);
      if (!person) continue; // no profile shard, so nothing to link to
      if (state.country && person.country !== state.country) continue;
      if (terms.length && !terms.every((t) => person.key.includes(t))) continue;
      totals = emptyTotals(nCounts, nMetrics);
      totalsById.set(id, totals);
    }
    addRow(totals, row);
  }

  const out = [];
  for (const [id, totals] of totalsById) {
    const comps = totals.counts[0];
    if (comps < state.minComps) continue;
    const person = people.get(id);
    out.push({
      id,
      name: person.name,
      country: person.country,
      comps,
      values: meta.metrics.map((m, i) => metricValue(totals, m, i, countIndex)),
    });
  }
  return out;
}

function sortRows(rows, meta, sort) {
  const position = new Map(meta.metrics.map((m, i) => [m.code, i]));
  const keyed = sort.map(({ key, dir }) => ({
    dir,
    get: position.has(key)
      ? (row) => row.values[position.get(key)]
      : key === "name" ? (row) => row.name
        : key === "country" ? (row) => row.country
          : (row) => row.comps,
  }));

  return rows.sort((a, b) => {
    for (const { dir, get } of keyed) {
      const x = get(a);
      const y = get(b);
      // Missing values sort last whichever way the column is pointing —
      // "no data" is not a good score or a bad one.
      const xNull = x === null || x === undefined || x === "";
      const yNull = y === null || y === undefined || y === "";
      if (xNull || yNull) {
        if (xNull && yNull) continue;
        return xNull ? 1 : -1;
      }
      if (x < y) return -dir;
      if (x > y) return dir;
    }
    return a.name.localeCompare(b.name);
  });
}

// ---- view ------------------------------------------------------------------

export async function render({ params }) {
  const meta = await getMeta();
  const levelGroups = meta.level_groups ?? [];
  const groups = meta.groups ?? [];

  const state = {
    pool: isPool(params.get("pool")) ? params.get("pool") : DEFAULT_POOL,
    query: params.get("q") ?? "",
    country: params.get("country") ?? "",
    minComps: Number(params.get("min") ?? DEFAULT_MIN_COMPS) || 0,
    from: Number(params.get("from")) || meta.season_min,
    to: Number(params.get("to")) || meta.season_max,
    levels: new Set(
      (params.get("lg") ?? (meta.default_level_groups ?? []).join(","))
        .split(",").filter((c) => levelGroups.some((g) => g.code === c))
    ),
    columns: new Set(
      (params.get("cols") ?? groups.map((g) => g.code).join(","))
        .split(",").filter((c) => groups.some((g) => g.code === c))
    ),
    // Opening on "most competitions" rather than on a metric: it is the one
    // ordering that puts fully-populated rows first (a mean placing sort tops
    // out with pre-2016 careers whose bout columns are all blank).
    sort: [{ key: "comps", dir: -1 }],
    selected: new Set(),
  };
  if (!state.levels.size) for (const g of levelGroups) state.levels.add(g.code);
  if (!state.columns.size) for (const g of groups) state.columns.add(g.code);

  let data = await loadPool(state.pool);

  // ---- controls ----

  const poolChips = chipRow("Weapon and gender", POOLS.map((p) => ({
    value: p.code, label: p.label, on: p.code === state.pool,
  })));

  const search = el("input", {
    class: "search-box", type: "search", id: "explore-search", autocomplete: "off",
    placeholder: "Filter by name — e.g. Kano", value: state.query,
  });

  const countrySelect = el("select", { class: "select", id: "explore-country", "aria-label": "Country" });
  const fromSelect = el("select", { class: "select", id: "explore-from", "aria-label": "First season" });
  const toSelect = el("select", { class: "select", id: "explore-to", "aria-label": "Last season" });
  const minInput = el("input", {
    class: "select num-input", type: "number", min: "1", step: "1",
    id: "explore-min", value: String(state.minComps),
  });

  function fillSelects() {
    countrySelect.replaceChildren(
      el("option", { value: "", text: "All countries", selected: !state.country }),
      ...data.countries.map((c) => el("option", { value: c, text: c, selected: c === state.country }))
    );
    const seasons = data.seasons;
    state.from = Math.min(Math.max(state.from, seasons[0]), seasons[seasons.length - 1]);
    state.to = Math.min(Math.max(state.to, seasons[0]), seasons[seasons.length - 1]);
    fromSelect.replaceChildren(...seasons.map((s) =>
      el("option", { value: s, text: s, selected: s === state.from })));
    toSelect.replaceChildren(...seasons.map((s) =>
      el("option", { value: s, text: s, selected: s === state.to })));
  }
  fillSelects();

  const levelChips = chipRow("Competition level", levelGroups.map((g) => ({
    value: g.code, label: g.label, on: state.levels.has(g.code),
  })));
  const columnChips = chipRow("Column groups", groups.map((g) => ({
    value: g.code, label: g.label, on: state.columns.has(g.code),
  })));

  const status = el("p", { class: "small muted", "aria-live": "polite" });
  const selectionBar = el("div", { class: "selection-bar" });
  const head = el("thead");
  const body = el("tbody");
  const table = el("table", { class: "explore-table" }, [head, body]);
  const scroller = el("div", { class: "table-scroll" }, [table]);

  // ---- rendering ----

  function visibleMetrics() {
    return meta.metrics
      .map((m, i) => ({ metric: m, position: i }))
      .filter(({ metric }) => state.columns.has(metric.group));
  }

  function sortIndicator(key) {
    const at = state.sort.findIndex((s) => s.key === key);
    if (at < 0) return "";
    const arrow = state.sort[at].dir === 1 ? "▲" : "▼";
    return state.sort.length > 1 ? ` ${arrow}${at + 1}` : ` ${arrow}`;
  }

  function headerCell({ key, label, title, num }) {
    const at = state.sort.findIndex((s) => s.key === key);
    const button = el("button", {
      type: "button", class: "th-sort", "data-key": key,
      title: title ? `${title} — click to sort, shift-click to add a second key` : "Click to sort, shift-click to add a second key",
    }, [`${label}${sortIndicator(key)}`]);
    return el("th", {
      class: [key === "name" ? "col-name" : null, num ? "num" : null].filter(Boolean).join(" ") || null,
      scope: "col",
      "aria-sort": at < 0 ? "none" : state.sort[at].dir === 1 ? "ascending" : "descending",
    }, [button]);
  }

  function draw() {
    const rows = sortRows(aggregate(data, meta, state), meta, state.sort);
    const shown = rows.slice(0, MAX_ROWS);
    const columns = visibleMetrics();

    head.replaceChildren(el("tr", {}, [
      el("th", { class: "col-pick", scope: "col" }, [el("span", { class: "sr-only", text: "Select" })]),
      ...FIXED_COLUMNS.map(headerCell),
      ...columns.map(({ metric }) => headerCell({
        key: metric.code, label: metric.short, title: metric.label, num: true,
      })),
    ]));

    body.replaceChildren(...shown.map((row) => el("tr", {}, [
      el("td", { class: "col-pick" }, [
        el("input", {
          type: "checkbox", "data-id": row.id, checked: state.selected.has(row.id),
          "aria-label": `Select ${row.name}`,
        }),
      ]),
      el("th", { class: "col-name", scope: "row" }, [
        el("a", { href: fencerHref(row.id), text: row.name }),
      ]),
      el("td", { class: "flag", text: row.country || "—" }),
      el("td", { class: "num", text: fmtInt(row.comps) }),
      ...columns.map(({ metric, position }) =>
        el("td", { class: "num", text: formatMetric(row.values[position], metric.fmt) })),
    ])));

    status.textContent = rows.length === 0
      ? "No fencer matches those filters."
      : rows.length > MAX_ROWS
        ? `${fmtInt(rows.length)} fencers match — showing the first ${MAX_ROWS} by this sort.`
        : `${fmtInt(rows.length)} fencer${rows.length === 1 ? "" : "s"}.`;

    drawSelection();
    syncUrl();
  }

  function drawSelection() {
    if (!state.selected.size) {
      selectionBar.replaceChildren();
      return;
    }
    const ids = [...state.selected];
    const names = new Map([...data.people].map(([id, p]) => [id, p.name]));
    selectionBar.replaceChildren(
      el("span", { class: "small muted", text: `Selected (${ids.length}):` }),
      ...ids.map((id) => el("span", { class: "tag pick-tag" }, [
        el("a", { href: fencerHref(id), text: names.get(id) ?? `#${id}` }),
        el("button", { type: "button", class: "pick-drop", "data-drop": id, "aria-label": `Remove ${names.get(id) ?? id}` }, ["×"]),
      ])),
      ids.length === 2
        ? el("a", { class: "small", href: `#/h2h?a=${ids[0]}&b=${ids[1]}`, text: "Head-to-head →" })
        : el("span", { class: "small muted", text: "Pick exactly two for a head-to-head." })
    );
  }

  function syncUrl() {
    const q = new URLSearchParams({ pool: state.pool });
    if (state.query) q.set("q", state.query);
    if (state.country) q.set("country", state.country);
    if (state.minComps !== DEFAULT_MIN_COMPS) q.set("min", String(state.minComps));
    if (state.from !== data.seasons[0]) q.set("from", String(state.from));
    if (state.to !== data.seasons[data.seasons.length - 1]) q.set("to", String(state.to));
    q.set("lg", [...state.levels].join(","));
    q.set("cols", [...state.columns].join(","));
    // replaceState, not `location.hash = …`: this is the state the reader is
    // already looking at, so it must not push a history entry or re-route.
    history.replaceState(null, "", `#/explore?${q}`);
  }

  // ---- wiring ----

  let drawToken = 0;
  function redraw() {
    const token = ++drawToken;
    // Aggregating 35k rows is a few milliseconds, but it is enough to make
    // typing feel sticky if it runs on every keystroke synchronously.
    requestAnimationFrame(() => { if (token === drawToken) draw(); });
  }

  search.addEventListener("input", () => { state.query = search.value; redraw(); });
  countrySelect.addEventListener("change", () => { state.country = countrySelect.value; redraw(); });
  minInput.addEventListener("input", () => { state.minComps = Number(minInput.value) || 0; redraw(); });
  fromSelect.addEventListener("change", () => {
    state.from = Number(fromSelect.value);
    if (state.to < state.from) { state.to = state.from; fillSelects(); }
    redraw();
  });
  toSelect.addEventListener("change", () => {
    state.to = Number(toSelect.value);
    if (state.from > state.to) { state.from = state.to; fillSelects(); }
    redraw();
  });

  poolChips.addEventListener("click", async (ev) => {
    const button = ev.target.closest("button");
    if (!button || button.dataset.value === state.pool) return;
    state.pool = button.dataset.value;
    pressOnly(poolChips, button);
    status.textContent = "Loading this pool's metrics…";
    body.replaceChildren();
    state.selected.clear();
    data = await loadPool(state.pool);
    fillSelects();
    draw();
  });

  levelChips.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    toggle(state.levels, button.dataset.value);
    // An empty set would show an empty table with no way back; the last chip
    // standing stays pressed instead.
    if (!state.levels.size) state.levels.add(button.dataset.value);
    button.setAttribute("aria-pressed", state.levels.has(button.dataset.value) ? "true" : "false");
    redraw();
  });

  columnChips.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    toggle(state.columns, button.dataset.value);
    if (!state.columns.size) state.columns.add(button.dataset.value);
    button.setAttribute("aria-pressed", state.columns.has(button.dataset.value) ? "true" : "false");
    redraw();
  });

  head.addEventListener("click", (ev) => {
    const button = ev.target.closest("button.th-sort");
    if (!button) return;
    const { key } = button.dataset;
    const metric = meta.metrics.find((m) => m.code === key);
    const fixed = FIXED_COLUMNS.find((c) => c.key === key);
    const fresh = { key, dir: metric ? initialDirection(metric) : fixed.dir };
    const at = state.sort.findIndex((s) => s.key === key);
    if (ev.shiftKey) {
      // Legacy's multi-sort: shift-click appends a tie-breaker, or flips one
      // that is already in play.
      if (at < 0) state.sort.push(fresh);
      else state.sort[at].dir *= -1;
    } else {
      state.sort = [at === 0 ? { key, dir: -state.sort[0].dir } : fresh];
    }
    draw();
  });

  body.addEventListener("change", (ev) => {
    const box = ev.target.closest("input[type=checkbox]");
    if (!box) return;
    const id = Number(box.dataset.id);
    if (box.checked) state.selected.add(id);
    else state.selected.delete(id);
    drawSelection();
  });

  selectionBar.addEventListener("click", (ev) => {
    const button = ev.target.closest("button.pick-drop");
    if (!button) return;
    state.selected.delete(Number(button.dataset.drop));
    for (const box of body.querySelectorAll("input[type=checkbox]")) {
      box.checked = state.selected.has(Number(box.dataset.id));
    }
    drawSelection();
  });

  draw();

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Metrics explorer" }),
      el("p", { class: "muted" }, [
        "Every competition metric, aggregated over the seasons and competition levels you pick. ",
        el("a", { href: "#/methodology?s=glossary", text: "What each metric means →" }),
      ]),
    ]),
    el("section", { class: "card" }, [
      poolChips,
      el("div", { class: "filter-row" }, [
        el("div", { class: "grow" }, [
          el("label", { class: "small muted", for: "explore-search", text: "Fencer" }),
          search,
        ]),
        el("div", {}, [
          el("label", { class: "small muted", for: "explore-country", text: "Country" }),
          countrySelect,
        ]),
        el("div", {}, [
          el("label", { class: "small muted", for: "explore-from", text: "From season" }),
          fromSelect,
        ]),
        el("div", {}, [
          el("label", { class: "small muted", for: "explore-to", text: "To season" }),
          toSelect,
        ]),
        el("div", {}, [
          el("label", { class: "small muted", for: "explore-min", text: "Min. comps" }),
          minInput,
        ]),
      ]),
      el("div", { class: "chip-block" }, [
        el("span", { class: "small muted", text: "Competition level" }),
        levelChips,
      ]),
      el("div", { class: "chip-block" }, [
        el("span", { class: "small muted", text: "Columns" }),
        columnChips,
      ]),
      status,
      selectionBar,
      scroller,
      el("p", { class: "small muted", text: "Means are taken over the competitions that actually carry the metric: pre-2016 events often have no bout data, so a fencer's poule and DE columns can rest on fewer competitions than their placings do." }),
    ]),
  ]);
}

// ---- small helpers ---------------------------------------------------------

function chipRow(label, items) {
  return el("div", { class: "pool-filter", role: "group", "aria-label": label },
    items.map((item) => el("button", {
      type: "button", text: item.label, "data-value": item.value,
      "aria-pressed": item.on ? "true" : "false",
    })));
}

function pressOnly(container, active) {
  for (const b of container.querySelectorAll("button")) {
    b.setAttribute("aria-pressed", b === active ? "true" : "false");
  }
}

function toggle(set, value) {
  if (set.has(value)) set.delete(value);
  else set.add(value);
}
