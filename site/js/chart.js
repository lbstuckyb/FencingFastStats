// Charts (ECharts, lazily loaded from the vendored bundle).
//
// Two of them: the single-series rating timeline on a profile, and the
// multi-series metric-over-time chart shared by the profile, the compare page
// and head-to-head.
//
// Design follows the project's dataviz rules: thin marks (2px lines, 8px
// symbols), a hairline recessive grid, a legend as soon as there is more than
// one series, direct end-labels only while they stay legible (<=4 series),
// crosshair + tooltip, and every colour read from a CSS token so light and
// dark stay in sync. Each chart ships with a `<details>` table view next to it
// — three of the light-mode series colours sit under 3:1 on the light surface,
// so the palette's relief rule applies.

let loaderPromise = null;

function loadECharts() {
  if (window.echarts) return Promise.resolve(window.echarts);
  if (!loaderPromise) {
    loaderPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "vendor/echarts.min.js"; // relative: works on any base path
      script.onload = () => resolve(window.echarts);
      script.onerror = () => {
        loaderPromise = null;
        reject(new Error("Could not load the charting library"));
      };
      document.head.append(script);
    });
  }
  return loaderPromise;
}

const token = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// The categorical slots, in the fixed order of the dataviz reference palette
// (validated for both surfaces — see css/style.css). A series' colour follows
// the fencer it belongs to, never their position in the current sort.
export const SERIES_SLOTS = 6;
export const seriesColor = (i) => token(`--series-${(i % SERIES_SLOTS) + 1}`) || "#2a78d6";

function palette() {
  return {
    textPrimary: token("--text-primary") || "#0b0b0b",
    textSecondary: token("--text-secondary") || "#52514e",
    gridLine: token("--border") || "#dedcd5",
    surface: token("--surface-1") || "#fcfcfb",
  };
}

/**
 * Initialises `container`, keeps the option in sync with resizes and theme
 * changes, and returns a dispose function. `build` is re-run on every theme
 * change so the colour tokens are re-read.
 */
async function mount(container, build) {
  const echarts = await loadECharts();
  const chart = echarts.init(container, null, { renderer: "svg" });
  let width = container.clientWidth;
  chart.setOption(build(width));

  const onResize = () => {
    chart.resize();
    // How many rows the legend wraps to depends on the width, and the grid has
    // to leave room for them. Rebuilding only on a real width change keeps the
    // two in step without throwing away legend toggles on every resize event.
    const next = container.clientWidth;
    if (Math.abs(next - width) > 24) {
      width = next;
      chart.setOption(build(width), true);
    }
  };
  const onTheme = () => chart.setOption(build(container.clientWidth), true);
  window.addEventListener("resize", onResize);
  window.addEventListener("ffs:themechange", onTheme);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", onTheme);

  return () => {
    window.removeEventListener("resize", onResize);
    window.removeEventListener("ffs:themechange", onTheme);
    media.removeEventListener("change", onTheme);
    chart.dispose();
  };
}

// ---- rating timeline -------------------------------------------------------

function ratingOption(points) {
  const { textPrimary, textSecondary, gridLine, surface } = palette();
  const series1 = seriesColor(0);

  const data = points.map((p) => [p.date, Math.round(p.post * 10) / 10]);
  const ratings = data.map((d) => d[1]);
  const lo = Math.min(...ratings);
  const hi = Math.max(...ratings);
  const pad = Math.max(20, (hi - lo) * 0.12);

  return {
    animation: false,
    backgroundColor: "transparent",
    grid: { left: 8, right: 56, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: gridLine, width: 1 } },
      backgroundColor: surface,
      borderColor: gridLine,
      borderWidth: 1,
      textStyle: { color: textPrimary, fontSize: 12 },
      formatter: (items) => {
        const item = items[0];
        const point = points[item.dataIndex];
        const date = new Date(`${point.date}T00:00:00Z`).toLocaleDateString("en-GB", {
          day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
        });
        const delta = point.post - point.pre;
        const sign = delta >= 0 ? "+" : "−";
        return `<strong>${Math.round(point.post)}</strong> rating<br>` +
          `<span style="color:${textSecondary}">${date} · ${sign}${Math.abs(delta).toFixed(1)} this event</span>`;
      },
    },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: gridLine } },
      axisTick: { show: false },
      axisLabel: { color: textSecondary, fontSize: 11, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      min: Math.floor((lo - pad) / 25) * 25,
      max: Math.ceil((hi + pad) / 25) * 25,
      axisLabel: { color: textSecondary, fontSize: 11 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: gridLine, width: 1, type: "solid" } },
    },
    series: [{
      type: "line",
      data,
      showSymbol: false,
      symbol: "circle",
      symbolSize: 8,
      lineStyle: { color: series1, width: 2, cap: "round", join: "round" },
      itemStyle: { color: series1, borderColor: surface, borderWidth: 2 },
      areaStyle: { color: series1, opacity: 0.1 },
      emphasis: { scale: 1, itemStyle: { color: series1, borderColor: surface, borderWidth: 2 } },
      endLabel: {
        show: true,
        color: textPrimary,
        fontSize: 12,
        fontWeight: 600,
        distance: 8,
        formatter: (p) => String(Math.round(p.value[1])),
      },
    }],
  };
}

/** Renders the rating timeline into `container`; returns a dispose function. */
export function renderRatingChart(container, points) {
  return mount(container, () => ratingOption(points));
}

// ---- metric over time ------------------------------------------------------

// A horizontal legend wraps on its own but never tells the grid it has grown,
// so on a phone the second row lands on top of the first y tick. The row count
// is estimated from the item widths — the key + its gaps, plus the label at
// roughly 6.6px per character at 12px — and the grid's top inset follows it.
const LEGEND_ROW = 22;

function estimateLegendRows(names, width) {
  const available = Math.max(160, (width || 640) - 8);
  let rows = 1;
  let used = 0;
  for (const name of names) {
    const item = 12 + 5 + name.length * 6.6 + 16;
    if (used && used + item > available) { rows += 1; used = item; }
    else used += item;
  }
  return rows;
}

// `series`: [{ name, points: [[x, value], …], colorIndex, dashed }]
//   x is a date string when `granularity` is "comp", a season number when it is
//   "season" and an age when it is "age" — they need different axis types, not
//   different charts.
// `axis`:   { label, reversed, format } — `format` is a value -> string
//   function, so the axis, the tooltip and the end-label all speak the metric's
//   own units (see metrics.formatMetric).
// `band`:   optional { name, colorIndex, xs, lower, upper } — a quantile band
//   drawn behind the lines as a 10% wash of its own hue (the area-fill spec).
//   It is silent and legend-less: the median line it belongs to carries the
//   identity, and its numbers ride that line's tooltip.
function metricOption(series, axis, granularity, band, width) {
  const { textPrimary, textSecondary, gridLine, surface } = palette();
  const multi = series.length > 1;
  // Past four lines a label at every line-end turns into a stack of collided
  // text; the legend and the tooltip carry identity from there on.
  const direct = series.length <= 4;
  const legendRows = multi ? estimateLegendRows(series.map((s) => s.name), width) : 0;

  // The band is one polygon between the two quantiles, drawn by a custom
  // series. Stacking two lines is the usual recipe and is wrong here: on a
  // cartesian value/value axis ECharts stacks the *x* dimension too, which
  // folds the band onto the baseline and doubles the x extent. The data is
  // still declared point-by-point with `encode` so both quantiles count
  // towards the axis extents; only the first item draws.
  const bandSeries = band ? [{
    type: "custom",
    name: `${band.name} band`,
    silent: true,
    z: 1,
    data: band.xs.map((x, i) => [x, band.lower[i], band.upper[i]]),
    encode: { x: 0, y: [1, 2] },
    renderItem: (params, api) => {
      if (params.dataIndex !== 0) return null;
      const top = band.xs.map((x, i) => api.coord([x, band.upper[i]]));
      const bottom = band.xs.map((x, i) => api.coord([x, band.lower[i]])).reverse();
      return {
        type: "polygon",
        shape: { points: [...top, ...bottom] },
        // The area-fill spec: the series hue as a ~10% wash, never a block.
        style: { fill: seriesColor(band.colorIndex ?? 0), opacity: 0.1 },
      };
    },
  }] : [];

  return {
    animation: false,
    backgroundColor: "transparent",
    grid: {
      left: 8,
      right: direct ? 96 : 16,
      top: legendRows ? 16 + legendRows * LEGEND_ROW : 16,
      // `containLabel` reserves room for the tick labels but not for the axis
      // name sitting under them.
      bottom: granularity === "age" ? 26 : 8,
      containLabel: true,
    },
    legend: multi ? {
      show: true,
      top: 0,
      left: 0,
      // Named explicitly so the band's two helper series stay out of it.
      data: series.map((s) => s.name),
      itemGap: 16,
      icon: "roundRect",
      itemWidth: 12,
      itemHeight: 3,
      textStyle: { color: textSecondary, fontSize: 12 },
      inactiveColor: gridLine,
    } : { show: false },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: gridLine, width: 1 } },
      backgroundColor: surface,
      borderColor: gridLine,
      borderWidth: 1,
      textStyle: { color: textPrimary, fontSize: 12 },
      formatter: (rawItems) => {
        // The band answers the axis pointer even though it is silent.
        const items = rawItems.filter((it) => !/ band$/.test(it.seriesName));
        if (!items.length) return "";
        const head = granularity === "season" ? `Season ${items[0].value[0]}`
          : granularity === "age" ? `Age ${items[0].value[0]}`
            : new Date(items[0].value[0]).toLocaleDateString("en-GB", {
              day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
            });
        const lines = items.map((it) =>
          `${it.marker}<span style="color:${textSecondary}">${it.seriesName}</span> ` +
          `<strong>${axis.format(it.value[1])}</strong>` +
          (it.data.note ? `<span style="color:${textSecondary}"> · ${it.data.note}</span>` : ""));
        return `<span style="color:${textSecondary}">${head}</span><br>${lines.join("<br>")}`;
      },
    },
    xAxis: granularity !== "comp"
      ? {
        type: "value",
        // Seasons and ages are counts, so the axis has to span the data rather
        // than reach back to zero the way a value axis does by default.
        min: "dataMin",
        max: "dataMax",
        minInterval: 1,
        // A bare row of numbers in the twenties reads as either; only the age
        // axis needs saying, and under the axis it can't collide with a tick.
        name: granularity === "age" ? "Age" : undefined,
        nameLocation: "middle",
        nameGap: 26,
        nameTextStyle: { color: textSecondary, fontSize: 11 },
        axisLine: { lineStyle: { color: gridLine } },
        axisTick: { show: false },
        axisLabel: { color: textSecondary, fontSize: 11, hideOverlap: true, formatter: (v) => String(v) },
        splitLine: { show: false },
      }
      : {
        type: "time",
        axisLine: { lineStyle: { color: gridLine } },
        axisTick: { show: false },
        axisLabel: { color: textSecondary, fontSize: 11, hideOverlap: true },
        splitLine: { show: false },
      },
    yAxis: {
      type: "value",
      // No axis name: the metric picker and the note under the chart both name
      // it, and an inverted axis puts a `nameLocation: "end"` label in the
      // bottom-left corner, on top of the first x tick.
      // A better place is a lower number, so the "good" end of the axis has to
      // be the top one — legacy reversed its POS axis for the same reason.
      inverse: Boolean(axis.reversed),
      scale: true,
      axisLabel: { color: textSecondary, fontSize: 11, formatter: (v) => axis.format(v) },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: gridLine, width: 1, type: "solid" } },
    },
    series: [...bandSeries, ...series.map((s) => {
      const color = seriesColor(s.colorIndex ?? 0);
      return {
        type: "line",
        z: 2,
        name: s.name,
        data: s.points,
        showSymbol: true,
        symbol: "circle",
        symbolSize: 8,
        connectNulls: false,
        lineStyle: {
          color,
          width: 2,
          cap: "round",
          join: "round",
          type: s.dashed ? "dashed" : "solid",
        },
        itemStyle: { color, borderColor: surface, borderWidth: 2 },
        emphasis: { scale: 1, itemStyle: { color, borderColor: surface, borderWidth: 2 } },
        endLabel: direct ? {
          show: true,
          color: textPrimary,
          fontSize: 11,
          fontWeight: 600,
          distance: 6,
          formatter: () => s.shortName ?? s.name,
        } : { show: false },
      };
    })],
  };
}

/** Renders a metric-over-time chart; returns a dispose function. */
export function renderMetricChart(container, { series, axis, granularity, band = null }) {
  return mount(container, (width) => metricOption(series, axis, granularity, band, width));
}
