// Rating-timeline chart (ECharts, lazily loaded from the vendored bundle).
//
// Design follows the project's dataviz rules: one series, so no legend box —
// the card title names it; 2px line, 10% area wash, hairline recessive grid,
// a direct end-label instead of per-point numbers, crosshair + tooltip, and
// the series colour taken from the CSS token so light/dark stay in sync
// (#2a78d6 / #3987e5, both validated against their surface).

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

function buildOption(points) {
  const series1 = token("--series-1") || "#2a78d6";
  const textPrimary = token("--text-primary") || "#0b0b0b";
  const textSecondary = token("--text-secondary") || "#52514e";
  const gridLine = token("--border") || "#dedcd5";
  const surface = token("--surface-1") || "#fcfcfb";

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
export async function renderRatingChart(container, points) {
  const echarts = await loadECharts();
  const chart = echarts.init(container, null, { renderer: "svg" });
  chart.setOption(buildOption(points));

  const onResize = () => chart.resize();
  const onTheme = () => chart.setOption(buildOption(points), true);
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
