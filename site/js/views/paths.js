// Trajectories: what a career looks like by age, for a cohort and for the
// fencers the reader overlays on it.
//
// The cohort curves come pre-computed from `data/paths/{pool}.json` — for every
// tier and every series, `{age: [n, mean, p25, p50, p75]}` (see
// `build_site.build_paths`). A cohort is "every fencer whose peak
// **FencingFastStats rating** ever put them in the top N of this pool": this
// site's own measure, computed from bout results, never an FIE ranking. The
// page says so wherever a tier is named.
//
// An overlaid fencer's own curve is computed here from their shard, by the same
// rule the cohort was built with: one value per (fencer, age), where a mean
// divides by the competitions that actually carry the metric.

import {
  DEFAULT_POOL, POOLS, getFencer, getMeta, getPaths, isPool, poolLabel,
} from "../data.js";
import {
  aggregateResults, formatMetric, groupsOf, metricAxis, metricsOf,
} from "../metrics.js";
import { fencerPicker, fencerSearchIndex } from "../picker.js";
import { chipRow, el, fencerHref, fmtInt, pressOnly } from "../util.js";

// The cohort median owns colour slot 0, so five fencers fill the palette's six
// categorical slots exactly (see chart.js).
const MAX_FENCERS = 5;
const DEFAULT_TIER = "top10";
const DEFAULT_METRIC = "rating";

// Point layout of `paths/{pool}.json`.
const P_N = 0, P_MEAN = 1, P25 = 2, P50 = 3, P75 = 4;

// ---- the metric catalogue --------------------------------------------------
// Registry metrics plus the by-year series that only exist on this page
// (rating, competitions entered, and the round-entry rates). Both kinds carry
// `label`/`short`/`fmt`/`better`/`blurb`, so everything downstream — the axis,
// the formatting, the tooltip — treats them the same.

const pathSeries = (meta) => meta.path_series ?? [];

function catalogue(meta) {
  return new Map([...metricsOf(meta), ...pathSeries(meta)].map((m) => [m.code, m]));
}

// ---- a fencer's own by-age curve -------------------------------------------

/** Calendar year minus birth year — the same age `build_paths` computes. */
const ageOf = (row, birthYear) => Number(String(row.date ?? "").slice(0, 4)) - birthYear;

function rowsByAge(fencer, weapon, gender) {
  const byAge = new Map();
  if (!fencer.birth_year) return byAge;
  for (const row of fencer.results ?? []) {
    if (row.weapon !== weapon || row.gender !== gender) continue;
    const age = ageOf(row, fencer.birth_year);
    if (!Number.isFinite(age)) continue;
    if (!byAge.has(age)) byAge.set(age, []);
    byAge.get(age).push(row);
  }
  return byAge;
}

/** The rating a fencer carried away from their last competition of that year. */
function ratingByAge(fencer, weapon, gender) {
  const byAge = new Map();
  if (!fencer.birth_year) return byAge;
  for (const point of fencer.rating_timeline ?? []) {
    if (point.weapon !== weapon || point.gender !== gender) continue;
    const age = ageOf(point, fencer.birth_year);
    if (Number.isFinite(age)) byAge.set(age, point.post); // the timeline is in date order
  }
  return byAge;
}

/** Mean of a per-competition predicate over the rows that carry the value. */
function rate(rows, position, predicate) {
  let n = 0;
  let hits = 0;
  for (const row of rows) {
    const value = row.m?.[position];
    if (value === null || value === undefined) continue;
    n += 1;
    if (predicate(value)) hits += 1;
  }
  return n ? hits / n : null;
}

/**
 * One `{age -> value}` map for the chosen series, computed from the fencer's
 * shard exactly as the cohort's own per-(fencer, age) values were.
 */
function fencerCurve(fencer, code, meta, weapon, gender) {
  if (code === "rating") return ratingByAge(fencer, weapon, gender);

  const positionOf = (c) => metricsOf(meta).findIndex((m) => m.code === c);
  const byAge = rowsByAge(fencer, weapon, gender);
  const out = new Map();
  for (const [age, rows] of byAge) {
    let value;
    if (code === "n_comps") value = rows.length;
    else if (code === "rate_t64") value = rate(rows, positionOf("T64+"), (v) => v > 0);
    else if (code === "rate_tpre64") value = rate(rows, positionOf("TPRE64"), (v) => v > 0);
    else if (code === "rate_podium") value = rate(rows, positionOf("POS"), (v) => v <= 3);
    else if (code === "rate_title") value = rate(rows, positionOf("POS"), (v) => v === 1);
    else value = aggregateResults(rows, meta)[positionOf(code)];
    if (value !== null && value !== undefined && !Number.isNaN(value)) out.set(age, value);
  }
  return out;
}

/** The pools a fencer has results in — what to offer when this one is empty. */
function poolsOf(fencer) {
  const codes = new Set((fencer.results ?? []).map((r) => `${r.weapon}${r.gender}`.toLowerCase()));
  return POOLS.filter((p) => codes.has(p.code));
}

// ---- view ------------------------------------------------------------------

const parseIds = (raw) => [...new Set(
  (raw ?? "").split(",").map((s) => Number(s.trim())).filter((n) => Number.isFinite(n) && n > 0)
)].slice(0, MAX_FENCERS);

export async function render({ params }) {
  const meta = await getMeta();
  const byCode = catalogue(meta);
  const tiers = meta.cohort_tiers ?? [];

  const wantedMetric = params.get("metric");
  const wantedTier = params.get("tier");
  const state = {
    pool: isPool(params.get("pool")) ? params.get("pool") : DEFAULT_POOL,
    tier: tiers.some((t) => t.code === wantedTier) ? wantedTier : DEFAULT_TIER,
    metric: byCode.has(wantedMetric) ? wantedMetric : DEFAULT_METRIC,
  };

  let file = await getPaths(state.pool);
  // Overlaid fencers, in the order the reader picked them: a fencer's colour
  // must not move when another is dropped.
  const fencers = (await Promise.all(parseIds(params.get("ids")).map((id) => getFencer(id).catch(() => null))))
    .filter(Boolean);

  // ---- controls ----

  const poolChips = chipRow("Weapon and gender", POOLS.map((p) => ({
    value: p.code, label: p.label, on: p.code === state.pool,
  })));
  const tierChips = chipRow("Cohort", tiers.map((t) => ({
    value: t.code,
    label: t.label,
    title: t.n
      ? `Fencers whose peak FencingFastStats rating ever put them in the top ${t.n} of this pool`
      : "Every fencer with a profile in this pool",
  })));
  const metricSelect = el("select", { class: "select", id: "paths-metric", "aria-label": "Series" }, [
    el("optgroup", { label: "Trajectory" }, pathSeries(meta).map((m) => el("option", {
      value: m.code, text: m.label, title: m.blurb, selected: m.code === state.metric,
    }))),
    ...groupsOf(meta).map((group) => el("optgroup", { label: group.label }, metricsOf(meta)
      .filter((m) => m.group === group.code)
      .map((m) => el("option", {
        value: m.code, text: m.label, title: m.blurb, selected: m.code === state.metric,
      })))),
  ]);

  const picked = el("div", { class: "selection-bar" });
  // Kept out of the selection bar: it is a flex row, and a paragraph dropped
  // into it lands beside the tags rather than under them.
  const pickedNotes = el("div");
  const pickerSlot = el("div");
  const plot = el("div", { class: "chart", role: "img" });
  const note = el("p", { class: "small muted chart-note" });
  const tableView = el("details", { class: "table-view" }, [el("summary", { text: "Show as a table" })]);
  const cohortNote = el("p", { class: "small muted" });

  // ---- drawing ----

  let dispose = null;

  function cohortPoints() {
    const metric = byCode.get(state.metric);
    const points = file.tiers?.[state.tier]?.series?.[state.metric] ?? {};
    const ages = Object.keys(points).map(Number).sort((a, b) => a - b);
    const fmt = (v) => formatMetric(v, metric.fmt);
    return {
      ages,
      median: ages.map((age) => {
        const p = points[String(age)];
        return {
          value: [age, p[P50]],
          note: `median of ${fmtInt(p[P_N])} · mean ${fmt(p[P_MEAN])} · middle half ${fmt(p[P25])}–${fmt(p[P75])}`,
        };
      }),
      lower: ages.map((age) => points[String(age)][P25]),
      upper: ages.map((age) => points[String(age)][P75]),
      raw: points,
    };
  }

  function buildSeries(cohort) {
    const { weapon, gender } = POOLS.find((p) => p.code === state.pool);
    const tier = tiers.find((t) => t.code === state.tier);
    const series = [];

    if (cohort.median.length) {
      series.push({
        name: `${tier.label} cohort (median)`,
        shortName: "Cohort",
        points: cohort.median,
        colorIndex: 0,
      });
    }
    fencers.forEach((fencer, i) => {
      const curve = fencerCurve(fencer, state.metric, meta, weapon, gender);
      const ages = [...curve.keys()].sort((a, b) => a - b);
      if (!ages.length) return;
      series.push({
        name: fencer.name,
        shortName: (fencer.name ?? `#${fencer.id}`).split(" ")[0],
        points: ages.map((age) => ({ value: [age, curve.get(age)] })),
        colorIndex: i + 1, // slot 0 belongs to the cohort
      });
    });
    return series;
  }

  function drawSelection() {
    const { weapon, gender } = POOLS.find((p) => p.code === state.pool);
    const cohortIds = new Set(file.cohort_ids?.[state.tier] ?? []);
    const tier = tiers.find((t) => t.code === state.tier);

    picked.replaceChildren(
      fencers.length
        ? el("span", { class: "small muted", text: "Overlaid:" })
        : el("span", { class: "small muted", text: "No fencer overlaid yet — the cohort curve is shown on its own." }),
      ...fencers.map((f) => el("span", { class: "tag pick-tag" }, [
        el("a", { href: fencerHref(f.id), text: f.name }),
        cohortIds.has(f.id)
          ? el("span", { class: "small muted", text: ` · in the ${tier.label}` })
          : null,
        el("button", {
          type: "button", class: "pick-drop", "data-drop": f.id,
          "aria-label": `Remove ${f.name}`,
        }, ["×"]),
      ])),
    );

    // A fencer with nothing in this pool would otherwise just be an absent line.
    pickedNotes.replaceChildren(
      ...fencers
        .filter((f) => !rowsByAge(f, weapon, gender).size)
        .map((f) => {
          const elsewhere = poolsOf(f).map((p) => p.label);
          return el("p", { class: "small muted", text:
            `${f.name} has no ${poolLabel(state.pool)} competition on record` +
            (elsewhere.length ? ` — they fence ${elsewhere.join(", ")}.` : ".") });
        })
    );
  }

  function drawTable(cohort, series) {
    const metric = byCode.get(state.metric);
    const fmt = (v) => formatMetric(v, metric.fmt);
    const overlays = series.filter((s) => s.colorIndex > 0);
    const lookup = overlays.map((s) => new Map(s.points.map((p) => [p.value[0], p.value[1]])));

    const ages = [...new Set([
      ...cohort.ages,
      ...overlays.flatMap((s) => s.points.map((p) => p.value[0])),
    ])].sort((a, b) => a - b);

    tableView.replaceChildren(
      el("summary", { text: "Show as a table" }),
      el("div", { class: "table-scroll" }, [
        el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { scope: "col", text: "Age" }),
              el("th", { class: "num", scope: "col", text: "Cohort n" }),
              el("th", { class: "num", scope: "col", text: "p25" }),
              el("th", { class: "num", scope: "col", text: "Median" }),
              el("th", { class: "num", scope: "col", text: "p75" }),
              el("th", { class: "num", scope: "col", text: "Mean" }),
              ...overlays.map((s) => el("th", { class: "num", scope: "col", text: s.name })),
            ]),
          ]),
          el("tbody", {}, ages.map((age) => {
            const p = cohort.raw[String(age)];
            return el("tr", {}, [
              el("th", { scope: "row", text: String(age) }),
              el("td", { class: "num", text: p ? fmtInt(p[P_N]) : "—" }),
              el("td", { class: "num", text: p ? fmt(p[P25]) : "—" }),
              el("td", { class: "num", text: p ? fmt(p[P50]) : "—" }),
              el("td", { class: "num", text: p ? fmt(p[P75]) : "—" }),
              el("td", { class: "num", text: p ? fmt(p[P_MEAN]) : "—" }),
              ...lookup.map((map) => el("td", { class: "num", text: fmt(map.get(age) ?? null) })),
            ]);
          })),
        ]),
      ])
    );
  }

  async function draw() {
    const metric = byCode.get(state.metric);
    const tier = tiers.find((t) => t.code === state.tier);
    const cohort = cohortPoints();
    const series = buildSeries(cohort);
    const axis = metricAxis(metric);

    drawSelection();
    drawTable(cohort, series);

    const athletes = file.tiers?.[state.tier]?.n_athletes ?? 0;
    cohortNote.textContent =
      `${tier.label}: ${fmtInt(athletes)} ${poolLabel(state.pool)} fencers whose peak ` +
      "FencingFastStats rating — this site's own rating, computed from bout results, not an " +
      `FIE ranking — ever placed them ${tier.n ? `in the top ${tier.n} of the pool` : "anywhere in the pool"}. ` +
      "The band is the middle half of the cohort at each age; ages with fewer than three " +
      "fencers on record are left out. A fencer's own curve reflects only the competitions " +
      "fie.org's archive holds for them.";

    note.textContent = cohort.median.length
      ? `${metric.label} — ${metric.blurb} ` +
        `Cohort ages ${cohort.ages[0]}–${cohort.ages[cohort.ages.length - 1]}.`
      : `No age in this cohort has enough fencers on record for ${metric.label}.`;
    plot.setAttribute("aria-label",
      `${metric.label} by age, ${series.length} series: ${series.map((s) => s.name).join(", ")}.`);

    if (dispose) { dispose(); dispose = null; }
    if (!series.length) {
      plot.replaceChildren(el("p", { class: "notice", text: "Nothing to plot for this cohort and series." }));
      return;
    }
    plot.replaceChildren();
    try {
      const { renderMetricChart } = await import("../chart.js");
      dispose = await renderMetricChart(plot, {
        series,
        axis,
        granularity: "age",
        band: cohort.ages.length
          ? { name: "Cohort", colorIndex: 0, xs: cohort.ages, lower: cohort.lower, upper: cohort.upper }
          : null,
      });
    } catch (err) {
      console.error(err);
      // The table view carries every plotted value, so a failed chart load
      // degrades rather than breaking the page.
      plot.replaceChildren(el("p", { class: "notice", text: "Chart unavailable — see the table below." }));
      tableView.setAttribute("open", "");
    }
  }

  function syncUrl() {
    const q = new URLSearchParams({ pool: state.pool, tier: state.tier, metric: state.metric });
    if (fencers.length) q.set("ids", fencers.map((f) => f.id).join(","));
    // replaceState: this is the view the reader is already looking at, so it
    // must not push a history entry or re-route the page.
    history.replaceState(null, "", `#/paths?${q}`);
  }

  function refresh() { syncUrl(); draw(); }

  // ---- picker ----

  async function drawPicker() {
    pickerSlot.replaceChildren();
    if (fencers.length >= MAX_FENCERS) {
      pickerSlot.append(el("p", { class: "small muted", text: `Up to ${MAX_FENCERS} fencers fit beside the cohort curve — remove one to add another.` }));
      return;
    }
    try {
      const index = await fencerSearchIndex();
      const chosen = new Set(fencers.map((f) => f.id));
      pickerSlot.append(fencerPicker({
        label: "Overlay a fencer",
        id: "paths-add",
        index: index.filter((e) => !chosen.has(e.i)),
        onPick: async (id) => {
          const fencer = await getFencer(id).catch(() => null);
          if (!fencer) {
            pickerSlot.append(el("p", { class: "small muted", text: `No profile for #${id} — profiles exist for fencers with at least two competitions.` }));
            return;
          }
          fencers.push(fencer);
          refresh();
          drawPicker();
        },
      }));
    } catch (err) {
      console.error(err);
      pickerSlot.append(el("p", { class: "notice", text: "The fencer index could not be loaded." }));
    }
  }

  // ---- wiring ----

  poolChips.addEventListener("click", async (ev) => {
    const button = ev.target.closest("button");
    if (!button || button.dataset.value === state.pool) return;
    state.pool = button.dataset.value;
    pressOnly(poolChips, button);
    file = await getPaths(state.pool);
    refresh();
  });
  tierChips.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button || button.dataset.value === state.tier) return;
    state.tier = button.dataset.value;
    pressOnly(tierChips, button);
    refresh();
  });
  metricSelect.addEventListener("change", () => { state.metric = metricSelect.value; refresh(); });
  picked.addEventListener("click", (ev) => {
    const button = ev.target.closest("button.pick-drop");
    if (!button) return;
    const at = fencers.findIndex((f) => f.id === Number(button.dataset.drop));
    if (at < 0) return;
    fencers.splice(at, 1);
    refresh();
    drawPicker();
  });

  pressOnly(tierChips, [...tierChips.querySelectorAll("button")].find((b) => b.dataset.value === state.tier));
  syncUrl();
  draw();
  drawPicker();

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Career trajectories" }),
      el("p", { class: "muted" }, [
        "How a cohort's season-by-season numbers develop with age, and how any fencer's own career sits against them. ",
        el("a", { href: "#/methodology?s=cohorts", text: "How the cohorts are built →" }),
      ]),
    ]),
    el("section", { class: "card" }, [
      poolChips,
      el("div", { class: "chip-block" }, [
        el("span", { class: "small muted", text: "Cohort (by peak FencingFastStats rating)" }),
        tierChips,
      ]),
      el("div", { class: "filter-row" }, [
        el("div", { class: "grow" }, [
          el("label", { class: "small muted", for: "paths-metric", text: "Series" }),
          metricSelect,
        ]),
      ]),
      picked,
      pickedNotes,
      pickerSlot,
      plot,
      note,
      tableView,
      cohortNote,
    ]),
  ]);
}
