// The advanced-metric views shared by the fencer profile, the compare page and
// head-to-head: one filter bar, one metric-over-time chart, one side-by-side
// comparison table, and (profile only) a season-by-season table.
//
// Everything is computed client-side from the fencers' own shards. Metrics are
// read through the registry (`metrics.js`) — labels, formats, aggregation and
// sort direction are never re-derived here — and means always divide by the
// population that actually carries the metric, exactly as the explorer does.

import { weaponName } from "./data.js";
import {
  aggregateResults, formatMetric, groupsOf, levelGrouper, metricAxis, metricsOf,
  resultValue, seasonOfResult,
} from "./metrics.js";
import { chipRow, el, fmtInt, toggle } from "./util.js";

// One line per fencer × weapon. Past eight the palette is out of distinct
// slots and the chart is unreadable anyway, so the thinnest series are cut.
const MAX_SERIES = 8;
const DEFAULT_METRIC = "POS";

// ---- state -----------------------------------------------------------------

/** Reads the shared filter state out of a route's query params. */
export function metricState(meta, params = new URLSearchParams()) {
  const metrics = metricsOf(meta);
  const levelGroups = meta.level_groups ?? [];
  const groups = groupsOf(meta);

  const wanted = params.get("metric");
  const state = {
    metric: metrics.some((m) => m.code === wanted) ? wanted : DEFAULT_METRIC,
    granularity: params.get("by") === "comp" ? "comp" : "season",
    from: Number(params.get("from")) || meta.season_min,
    to: Number(params.get("to")) || meta.season_max,
    levels: new Set(
      (params.get("lg") ?? levelGroups.map((g) => g.code).join(","))
        .split(",").filter((c) => levelGroups.some((g) => g.code === c))
    ),
    columns: new Set(
      (params.get("cols") ?? groups.map((g) => g.code).join(","))
        .split(",").filter((c) => groups.some((g) => g.code === c))
    ),
  };
  // Unlike the explorer, these views open on *every* competition level: a
  // profile that showed only World Cups would silently hide half a career.
  if (!state.levels.size) for (const g of levelGroups) state.levels.add(g.code);
  if (!state.columns.size) for (const g of groups) state.columns.add(g.code);
  return state;
}

/** The inverse: the state as query params, defaults omitted. */
export function metricParams(state, meta) {
  const q = new URLSearchParams();
  if (state.metric !== DEFAULT_METRIC) q.set("metric", state.metric);
  if (state.granularity === "comp") q.set("by", "comp");
  if (state.from !== meta.season_min) q.set("from", String(state.from));
  if (state.to !== meta.season_max) q.set("to", String(state.to));
  if (state.levels.size !== (meta.level_groups ?? []).length) q.set("lg", [...state.levels].join(","));
  return q;
}

// ---- aggregation -----------------------------------------------------------

export function filterResults(results, state, groupOf) {
  return (results ?? []).filter((r) => {
    const season = seasonOfResult(r);
    return season >= state.from && season <= state.to && state.levels.has(groupOf(r.level));
  });
}

/** `{season -> rows}`, ascending. */
function bySeason(rows) {
  const map = new Map();
  for (const row of rows) {
    const season = seasonOfResult(row);
    if (!map.has(season)) map.set(season, []);
    map.get(season).push(row);
  }
  return new Map([...map].sort((a, b) => a[0] - b[0]));
}

function byWeapon(rows) {
  const map = new Map();
  for (const row of rows) {
    if (!map.has(row.weapon)) map.set(row.weapon, []);
    map.get(row.weapon).push(row);
  }
  // Most-fenced weapon first, so the solid line is the fencer's main one.
  return new Map([...map].sort((a, b) => b[1].length - a[1].length));
}

/** One chart series per (fencer, weapon) that has a value to plot. */
function buildSeries(fencers, state, meta, groupOf) {
  const position = metricsOf(meta).findIndex((m) => m.code === state.metric);
  const metric = metricsOf(meta)[position];
  const series = [];

  fencers.forEach((fencer, index) => {
    const weapons = byWeapon(filterResults(fencer.results, state, groupOf));
    const multiWeapon = weapons.size > 1;
    let slot = 0;
    for (const [weapon, rows] of weapons) {
      const points = state.granularity === "season"
        ? [...bySeason(rows)].map(([season, seasonRows]) => {
          const value = aggregateResults(seasonRows, meta)[position];
          return value === null ? null : {
            value: [season, value],
            note: `${fmtInt(seasonRows.length)} comp${seasonRows.length === 1 ? "" : "s"}`,
          };
        }).filter(Boolean)
        : rows
          .map((row) => {
            const value = resultValue(row, position);
            return value === null ? null : { value: [row.date, value], note: row.name ?? "" };
          })
          .filter(Boolean)
          .sort((a, b) => (a.value[0] < b.value[0] ? -1 : 1));

      if (!points.length) continue;
      const surname = (fencer.name ?? `#${fencer.id}`).split(" ")[0];
      series.push({
        name: multiWeapon ? `${fencer.name} · ${weaponName(weapon)}` : fencer.name,
        shortName: multiWeapon ? `${surname} ${weapon}` : surname,
        points,
        colorIndex: index,
        // Colour stays with the fencer, so a second weapon is told apart by
        // its dash pattern rather than by a colour of its own.
        dashed: slot > 0,
      });
      slot += 1;
    }
  });

  // The cut keeps the fullest series; the legend keeps the order the reader
  // picked the fencers in, so a fencer's place in the legend doesn't jump
  // around as the filters change.
  const kept = new Set([...series].sort((a, b) => b.points.length - a.points.length).slice(0, MAX_SERIES));
  return {
    series: series.filter((s) => kept.has(s)),
    dropped: Math.max(0, series.length - MAX_SERIES),
    metric,
  };
}

// ---- the shared section ----------------------------------------------------

/**
 * Filter bar + metric chart (+ optional side-by-side comparison table) over
 * one or more fencer shards. Returns `{ node, refresh }`; `refresh()` re-reads
 * the state object the caller passed in.
 */
export function metricSection({ meta, fencers, state, onChange = () => {}, comparison = true, title = "Metric over time" }) {
  const groupOf = levelGrouper(meta);
  const metrics = metricsOf(meta);
  const levelGroups = meta.level_groups ?? [];
  const seasons = [];
  for (let s = meta.season_min; s <= meta.season_max; s += 1) seasons.push(s);

  // ---- controls ----
  const metricSelect = el("select", { class: "select", id: "metric-pick", "aria-label": "Metric" }, [
    ...groupsOf(meta).map((group) =>
      el("optgroup", { label: group.label }, metrics
        .filter((m) => m.group === group.code)
        .map((m) => el("option", {
          value: m.code, text: m.label, title: m.blurb, selected: m.code === state.metric,
        })))),
  ]);
  const granularityChips = chipRow("Points", [
    { value: "season", label: "Per season", on: state.granularity === "season" },
    { value: "comp", label: "Per competition", on: state.granularity === "comp" },
  ]);
  const fromSelect = el("select", { class: "select", id: "metric-from", "aria-label": "First season" },
    seasons.map((s) => el("option", { value: s, text: s, selected: s === state.from })));
  const toSelect = el("select", { class: "select", id: "metric-to", "aria-label": "Last season" },
    seasons.map((s) => el("option", { value: s, text: s, selected: s === state.to })));
  const levelChips = chipRow("Competition level", levelGroups.map((g) => ({
    value: g.code, label: g.label, on: state.levels.has(g.code),
  })));

  const plot = el("div", { class: "chart", role: "img" });
  const note = el("p", { class: "small muted chart-note" });
  const tableView = el("details", { class: "table-view" }, [el("summary", { text: "Show as a table" })]);
  const compareBody = el("div");
  const compareCard = comparison
    ? el("section", { class: "card" }, [
      el("h2", { text: fencers.length > 1 ? "Metric comparison" : "Career metrics" }),
      el("p", { class: "small muted", text: "Every metric over the seasons and levels selected above. The better value in each row is highlighted; metrics that are descriptive rather than good-or-bad are left unmarked." }),
      compareBody,
    ])
    : null;

  // ---- drawing ----
  let dispose = null;

  async function draw() {
    const { series, dropped, metric } = buildSeries(fencers, state, meta, groupOf);
    const axis = metricAxis(metric);

    const points = series.reduce((n, s) => n + s.points.length, 0);
    note.textContent = series.length
      ? `${metric.label} — ${metric.blurb} ` +
        `${fmtInt(points)} point${points === 1 ? "" : "s"}${dropped ? `, ${dropped} thinner series hidden` : ""}.`
      : "";
    plot.setAttribute(
      "aria-label",
      `${metric.label} over time, ${series.length} series: ${series.map((s) => s.name).join(", ")}.`
    );

    drawTableView(series, axis);
    if (comparison) compareBody.replaceChildren(comparisonTable(meta, fencers, state, groupOf));

    if (dispose) { dispose(); dispose = null; }
    if (!series.length) {
      plot.replaceChildren(el("p", { class: "notice", text: "No competition on record carries this metric under these filters." }));
      return;
    }
    plot.replaceChildren();
    try {
      const { renderMetricChart } = await import("./chart.js");
      dispose = await renderMetricChart(plot, { series, axis, granularity: state.granularity });
    } catch (err) {
      console.error(err);
      // The table view carries every plotted value, so a failed chart load
      // degrades rather than breaking the page.
      plot.replaceChildren(el("p", { class: "notice", text: "Chart unavailable — see the table below." }));
      tableView.setAttribute("open", "");
    }
  }

  function drawTableView(series, axis) {
    const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.value[0])))]
      .sort((a, b) => (a < b ? -1 : 1));
    const lookup = series.map((s) => new Map(s.points.map((p) => [p.value[0], p.value[1]])));

    tableView.replaceChildren(
      el("summary", { text: "Show as a table" }),
      el("div", { class: "table-scroll" }, [
        el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: state.granularity === "season" ? "Season" : "Date" }),
              ...series.map((s) => el("th", { class: "num", text: s.name })),
            ]),
          ]),
          el("tbody", {}, xs.map((x) =>
            el("tr", {}, [
              el("td", { class: "small nowrap", text: String(x) }),
              ...lookup.map((map) => el("td", { class: "num", text: axis.format(map.get(x) ?? null) })),
            ])
          )),
        ]),
      ])
    );
  }

  function changed() {
    onChange(state);
    draw();
  }

  // ---- wiring ----
  metricSelect.addEventListener("change", () => { state.metric = metricSelect.value; changed(); });
  granularityChips.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button || button.dataset.value === state.granularity) return;
    state.granularity = button.dataset.value;
    for (const b of granularityChips.querySelectorAll("button")) {
      b.setAttribute("aria-pressed", b === button ? "true" : "false");
    }
    changed();
  });
  fromSelect.addEventListener("change", () => {
    state.from = Number(fromSelect.value);
    if (state.to < state.from) { state.to = state.from; toSelect.value = String(state.to); }
    changed();
  });
  toSelect.addEventListener("change", () => {
    state.to = Number(toSelect.value);
    if (state.from > state.to) { state.from = state.to; fromSelect.value = String(state.from); }
    changed();
  });
  levelChips.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    toggle(state.levels, button.dataset.value);
    // An empty set leaves an empty chart with no way back; the last chip
    // standing stays pressed.
    if (!state.levels.size) state.levels.add(button.dataset.value);
    button.setAttribute("aria-pressed", state.levels.has(button.dataset.value) ? "true" : "false");
    changed();
  });

  draw();

  const chartCard = el("section", { class: "card" }, [
    el("h2", { text: title }),
    el("div", { class: "filter-row" }, [
      el("div", { class: "grow" }, [
        el("label", { class: "small muted", for: "metric-pick", text: "Metric" }),
        metricSelect,
      ]),
      el("div", {}, [
        el("label", { class: "small muted", for: "metric-from", text: "From season" }),
        fromSelect,
      ]),
      el("div", {}, [
        el("label", { class: "small muted", for: "metric-to", text: "To season" }),
        toSelect,
      ]),
    ]),
    el("div", { class: "chip-block" }, [
      el("span", { class: "small muted", text: "Competition level" }),
      levelChips,
    ]),
    el("div", { class: "chip-block" }, [
      el("span", { class: "small muted", text: "Points" }),
      granularityChips,
    ]),
    plot,
    note,
    tableView,
  ]);

  return { node: el("div", { class: "grid" }, [chartCard, compareCard]), refresh: draw };
}

// ---- comparison table ------------------------------------------------------

/** Every metric, one column per fencer, the better value marked. */
export function comparisonTable(meta, fencers, state, groupOf = levelGrouper(meta)) {
  const metrics = metricsOf(meta);
  const columns = fencers.map((fencer) => {
    const rows = filterResults(fencer.results, state, groupOf);
    return { fencer, n: rows.length, values: aggregateResults(rows, meta) };
  });

  const body = [];
  for (const group of groupsOf(meta)) {
    const inGroup = metrics
      .map((metric, i) => ({ metric, i }))
      .filter(({ metric }) => metric.group === group.code);
    if (!inGroup.length) continue;

    body.push(el("tr", { class: "group-row" }, [
      el("th", { scope: "colgroup", colspan: columns.length + 1, text: group.label }),
    ]));

    for (const { metric, i } of inGroup) {
      const values = columns.map((c) => c.values[i]);
      const best = bestIndex(values, metric.better);
      body.push(el("tr", {}, [
        el("th", { scope: "row", title: metric.blurb }, [
          metric.label,
          el("span", { class: "small muted", text: ` ${metric.code}` }),
        ]),
        ...values.map((v, ci) => el("td", {
          class: ci === best ? "num best" : "num",
          text: formatMetric(v, metric.fmt),
          title: ci === best && columns.length > 1 ? "Better" : null,
        })),
      ]));
    }
  }

  return el("div", { class: "table-scroll" }, [
    el("table", { class: "compare-table" }, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { scope: "col", text: "Metric" }),
          ...columns.map((c) => el("th", { class: "num", scope: "col" }, [
            el("a", { href: `#/fencer/${c.fencer.id}`, text: c.fencer.name }),
            el("div", { class: "small muted", text: `${fmtInt(c.n)} competition${c.n === 1 ? "" : "s"}` }),
          ])),
        ]),
      ]),
      el("tbody", {}, body),
    ]),
  ]);
}

// Which column holds the better value — `null` when the metric is descriptive
// (`better: null` in the registry) or nothing is comparable.
function bestIndex(values, better) {
  if (!better) return -1;
  let best = -1;
  values.forEach((v, i) => {
    if (v === null || v === undefined) return;
    if (best < 0) { best = i; return; }
    const current = values[best];
    if (better === "low" ? v < current : v > current) best = i;
  });
  // A lone value is not "better" than anything.
  return values.filter((v) => v !== null && v !== undefined).length > 1 ? best : -1;
}

// ---- season-by-season table ------------------------------------------------

/**
 * One row per season plus a whole-career row, aggregated exactly as the
 * explorer aggregates a filter selection. Returns `{ node, refresh }`.
 */
export function seasonTable({ meta, fencer, state }) {
  const groupOf = levelGrouper(meta);
  const metrics = metricsOf(meta);
  const groups = groupsOf(meta);

  const columnChips = chipRow("Column groups", groups.map((g) => ({
    value: g.code, label: g.label, on: state.columns.has(g.code),
  })));
  const head = el("thead");
  const body = el("tbody");
  const status = el("p", { class: "small muted", "aria-live": "polite" });

  function draw() {
    const visible = metrics
      .map((metric, i) => ({ metric, i }))
      .filter(({ metric }) => state.columns.has(metric.group));
    const rows = filterResults(fencer.results, state, groupOf);
    const seasons = [...bySeason(rows)].reverse();

    head.replaceChildren(el("tr", {}, [
      el("th", { scope: "col", text: "Season" }),
      el("th", { class: "num", scope: "col", text: "Comps" }),
      ...visible.map(({ metric }) => el("th", { class: "num", scope: "col", title: metric.label }, [metric.short])),
    ]));

    const line = (label, subset, className) => el("tr", { class: className ?? null }, [
      el("th", { scope: "row", text: label }),
      el("td", { class: "num", text: fmtInt(subset.length) }),
      ...(() => {
        const values = aggregateResults(subset, meta);
        return visible.map(({ metric, i }) =>
          el("td", { class: "num", text: formatMetric(values[i], metric.fmt) }));
      })(),
    ]);

    body.replaceChildren(
      ...(rows.length ? [line("All seasons", rows, "total-row")] : []),
      ...seasons.map(([season, seasonRows]) => line(String(season), seasonRows))
    );
    status.textContent = rows.length
      ? `${fmtInt(seasons.length)} season${seasons.length === 1 ? "" : "s"} under the filters above.`
      : "No competition matches the filters above.";
  }

  columnChips.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    toggle(state.columns, button.dataset.value);
    if (!state.columns.size) state.columns.add(button.dataset.value);
    button.setAttribute("aria-pressed", state.columns.has(button.dataset.value) ? "true" : "false");
    draw();
  });

  draw();

  return {
    node: el("section", { class: "card" }, [
      el("h2", { text: "Season by season" }),
      el("p", { class: "small muted", text: "Every metric aggregated over the seasons and levels selected above. Means are taken over the competitions that actually carry the metric, so poule and DE columns can rest on fewer competitions than placings do." }),
      el("div", { class: "chip-block" }, [
        el("span", { class: "small muted", text: "Columns" }),
        columnChips,
      ]),
      status,
      el("div", { class: "table-scroll" }, [el("table", { class: "season-table" }, [head, body])]),
    ]),
    refresh: draw,
  };
}
