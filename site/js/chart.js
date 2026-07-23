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
  chart.setOption(build());

  const onResize = () => chart.resize();
  const onTheme = () => chart.setOption(build(), true);
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

// `series`: [{ name, points: [[x, value], …], colorIndex, dashed }]
//   x is a date string when `granularity` is "comp" and a season number when it
//   is "season" — the two need different axis types, not different charts.
// `axis`:   { label, reversed, format } — `format` is a value -> string
//   function, so the axis, the tooltip and the end-label all speak the metric's
//   own units (see metrics.formatMetric).
function metricOption(series, axis, granularity) {
  const { textPrimary, textSecondary, gridLine, surface } = palette();
  const multi = series.length > 1;
  // Past four lines a label at every line-end turns into a stack of collided
  // text; the legend and the tooltip carry identity from there on.
  const direct = series.length <= 4;

  return {
    animation: false,
    backgroundColor: "transparent",
    grid: { left: 8, right: direct ? 96 : 16, top: multi ? 40 : 16, bottom: 8, containLabel: true },
    legend: multi ? {
      show: true,
      top: 0,
      left: 0,
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
      formatter: (items) => {
        if (!items.length) return "";
        const head = granularity === "season"
          ? `Season ${items[0].value[0]}`
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
    xAxis: granularity === "season"
      ? {
        type: "value",
        // Seasons are years, so the axis has to span the data rather than
        // reach back to zero the way a value axis does by default.
        min: "dataMin",
        max: "dataMax",
        minInterval: 1,
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
    series: series.map((s) => {
      const color = seriesColor(s.colorIndex ?? 0);
      return {
        type: "line",
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
    }),
  };
}

/** Renders a metric-over-time chart; returns a dispose function. */
export function renderMetricChart(container, { series, axis, granularity }) {
  return mount(container, () => metricOption(series, axis, granularity));
}
