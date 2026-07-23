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
