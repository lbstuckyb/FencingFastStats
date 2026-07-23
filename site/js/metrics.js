// Everything that reads `meta.json`'s metric registry: formatting, default
// sort direction, and the re-aggregation of the explorer's pre-summed rows.
//
// The registry (src/ffs/metrics.py, serialized into meta.json) is the single
// source of truth for a metric's label, aggregation and sort direction — no
// view hardcodes any of the three.

import { fmtInt, fmtNum } from "./util.js";

export const metricsOf = (meta) => meta?.metrics ?? [];
export const groupsOf = (meta) => meta?.groups ?? [];

export function metricByCode(meta) {
  return new Map(metricsOf(meta).map((m) => [m.code, m]));
}

// Position of each metric in a shard's `m` array and in an explorer row's sums:
// both are written in registry order.
export function metricPositions(meta) {
  return new Map(metricsOf(meta).map((m, i) => [m.code, i]));
}

export function formatMetric(value, fmt) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  switch (fmt) {
    case "int": return fmtInt(Math.round(value));
    case "pct": return `${fmtNum(value * 100, 1)}%`;
    case "float2": return fmtNum(value, 2);
    default: return fmtNum(value, 1);
  }
}

// Which way a column sorts when it is first clicked: the better end of the
// scale comes first. Descriptive metrics (`better: null`) start descending,
// like any other "show me the big numbers" column.
export const initialDirection = (metric) => (metric?.better === "low" ? 1 : -1);

// ---- explorer rows ---------------------------------------------------------
// A row is `[athlete_id, season, level_group_index, ...counts, ...metric_sums]`
// holding sums, never means: the client adds up whatever the filters select and
// divides once, at the end. (The mean of per-season means is not the mean.)

export const ROW_ATHLETE = 0;
export const ROW_SEASON = 1;
export const ROW_LEVEL_GROUP = 2;
export const ROW_COUNTS = 3;

export function emptyTotals(nCounts, nMetrics) {
  return { counts: new Array(nCounts).fill(0), sums: new Array(nMetrics).fill(null) };
}

export function addRow(totals, row) {
  const nCounts = totals.counts.length;
  for (let i = 0; i < nCounts; i += 1) totals.counts[i] += row[ROW_COUNTS + i];
  const offset = ROW_COUNTS + nCounts;
  for (let i = 0; i < totals.sums.length; i += 1) {
    const v = row[offset + i];
    // `null` means "no competition in this row had a value" — distinct from a
    // real 0, so it must not seed the sum.
    if (v !== null && v !== undefined) totals.sums[i] = (totals.sums[i] ?? 0) + v;
  }
}

// `countIndex` maps a metric's `den` to its slot in the counts array; a mean
// is only correct over the population that actually carries the metric (see
// metrics.COUNT_SOURCE — pre-2016 competitions have no bout data at all).
export function countIndexOf(meta) {
  return new Map((meta?.counts ?? []).map((key, i) => [key, i]));
}

export function metricValue(totals, metric, position, countIndex) {
  const sum = totals.sums[position];
  if (sum === null || sum === undefined) return null;
  if (metric.agg === "sum") return sum;
  const denominator = totals.counts[countIndex.get(metric.den)];
  return denominator ? sum / denominator : null;
}

// ---- fencer-shard rows -----------------------------------------------------
// A profile's own results carry raw per-competition values (`m`, in registry
// order) rather than the explorer's pre-summed rows, so the same aggregation
// has to be done here from scratch — same rule, same denominators.

// Which column's non-null count each `den` is taken over. This reproduces
// `metrics.COUNT_SOURCE` without shipping it: the representative column is the
// first metric in registry order carrying that `den`, which is exactly how the
// Python side picks it (POS for `comps`, PVICT for `poule`, TTR for `de`, …).
export function denPositions(meta) {
  const positions = new Map();
  metricsOf(meta).forEach((m, i) => {
    if (!positions.has(m.den)) positions.set(m.den, i);
  });
  return positions;
}

/**
 * Aggregates raw shard result rows into one value per metric: sums are summed,
 * means are the sum divided by the population the metric actually has data for
 * — never by the number of competitions entered.
 */
export function aggregateResults(rows, meta) {
  const metrics = metricsOf(meta);
  const dens = denPositions(meta);

  const sums = new Array(metrics.length).fill(null);
  const counts = new Array(metrics.length).fill(0);
  for (const row of rows) {
    const values = row.m ?? [];
    for (let i = 0; i < metrics.length; i += 1) {
      const v = values[i];
      if (v === null || v === undefined) continue;
      sums[i] = (sums[i] ?? 0) + v;
      counts[i] += 1;
    }
  }

  return metrics.map((metric, i) => {
    const sum = sums[i];
    if (sum === null) return null;
    if (metric.agg === "sum") return sum;
    const denominator = counts[dens.get(metric.den) ?? i];
    return denominator ? sum / denominator : null;
  });
}

/** The value of one metric on a single result row, by registry position. */
export const resultValue = (row, position) => row.m?.[position] ?? null;

// The season a result belongs to is the one baked into its competition id
// ("2026-799"), which is fie.org's own season rather than the calendar year of
// the date — a September competition belongs to the season that has just begun.
export function seasonOfResult(row) {
  const season = Number(String(row.competition_id ?? "").split("-")[0]);
  return Number.isFinite(season) ? season : Number(String(row.date ?? "").slice(0, 4));
}

/** `level` code -> level-group code, with the registry's catch-all group. */
export function levelGrouper(meta) {
  const byLevel = new Map();
  let fallback = "OTH";
  for (const group of meta?.level_groups ?? []) {
    for (const level of group.levels ?? []) byLevel.set(level, group.code);
    if (!(group.levels ?? []).length) fallback = group.code;
  }
  return (level) => byLevel.get(level) ?? fallback;
}

/** Axis description for the metric chart: units, direction, label. */
export function metricAxis(metric) {
  return {
    label: metric.short,
    // A better place is a *lower* number, so the good end of the axis has to be
    // the top one.
    reversed: metric.better === "low",
    format: (v) => formatMetric(v, metric.fmt),
  };
}
