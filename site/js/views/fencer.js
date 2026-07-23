// Fencer profile: career summary, rating timeline chart, full results history
// and top rivals, from data/fencers/{id%100}/{id}.json.

import { getFencer, getMeta, weaponName } from "../data.js";
import { el, fencerLink, fmtDate, fmtInt, fmtNum, seasonOf } from "../util.js";

// Result rows carry their metrics as a fixed-order array (`m`) keyed by
// `meta.json`'s registry, so nothing here hardcodes a column position.
function metricReader(meta) {
  const index = new Map((meta?.metrics ?? []).map((m, i) => [m.code, i]));
  return (row, code) => {
    const i = index.get(code);
    return i === undefined ? null : row.m?.[i] ?? null;
  };
}

function head(f) {
  const bits = [
    f.country,
    f.birth_year ? `b. ${f.birth_year}` : null,
    f.hand ? `${f.hand}-handed` : null,
  ].filter(Boolean);

  return el("div", { class: "page-head" }, [
    el("div", { class: "profile-head" }, [
      el("h1", { text: f.name || `Fencer #${f.id}` }),
      el("span", { class: "meta", text: bits.join(" · ") }),
    ]),
  ]);
}

function careerCards(f) {
  return el(
    "div",
    { class: "grid grid-3" },
    f.career.map((c) =>
      el("section", { class: "card" }, [
        el("h2", { text: weaponName(c.weapon) }),
        el("div", { class: "stat-row" }, [
          stat("Competitions", fmtInt(c.n_comps)),
          stat("Best finish", c.best_rank ? `#${c.best_rank}` : "—"),
          stat("Titles", fmtInt(c.titles)),
          stat("Rating", c.current_rating ? fmtNum(c.current_rating, 0) : "—"),
        ]),
      ])
    )
  );
}

function stat(label, value) {
  return el("div", { class: "stat" }, [
    el("span", { class: "label", text: label }),
    el("span", { class: "value", text: value }),
  ]);
}

function ratingCard(f) {
  const timeline = [...f.rating_timeline].sort((a, b) => (a.date < b.date ? -1 : 1));

  // Ratings are per weapon pool, so a multi-weapon fencer gets one line per
  // weapon behind a selector — never one line mixing two rating scales. A
  // weapon with a single rated competition has no line to draw, so it's left
  // out entirely rather than offered as an empty chart.
  const counts = new Map();
  for (const p of timeline) counts.set(p.weapon, (counts.get(p.weapon) ?? 0) + 1);
  const weapons = [...counts.keys()]
    .filter((w) => counts.get(w) >= 2)
    .sort((a, b) => counts.get(b) - counts.get(a));

  if (!weapons.length) {
    return el("section", { class: "card" }, [
      el("h2", { text: "Rating over time" }),
      el("p", { class: "notice", text: "Not enough rated competitions to plot a timeline." }),
    ]);
  }
  let active = weapons[0];

  const plot = el("div", { class: "chart", role: "img" });
  const note = el("p", { class: "small muted chart-note" });
  const tableWrap = el("details", { class: "table-view" }, [
    el("summary", { text: "Show as a table" }),
  ]);

  const card = el("section", { class: "card" }, [
    el("h2", { text: "Rating over time" }),
    el("p", { class: "small muted", text: "Elo rating after every competition on record." }),
  ]);

  if (weapons.length > 1) {
    const picker = el(
      "div",
      { class: "pool-filter", role: "group", "aria-label": "Weapon" },
      weapons.map((w) =>
        el("button", {
          type: "button",
          text: weaponName(w),
          "data-weapon": w,
          "aria-pressed": w === active ? "true" : "false",
        })
      )
    );
    picker.addEventListener("click", (ev) => {
      const button = ev.target.closest("button");
      if (!button || button.dataset.weapon === active) return;
      active = button.dataset.weapon;
      for (const b of picker.querySelectorAll("button")) {
        b.setAttribute("aria-pressed", b === button ? "true" : "false");
      }
      draw();
    });
    card.append(picker);
  }

  card.append(plot, note, tableWrap);

  let dispose = null;
  async function draw() {
    const points = timeline.filter((p) => p.weapon === active);
    const first = points[0];
    const last = points[points.length - 1];
    const peak = points.reduce((m, p) => (p.post > m.post ? p : m), points[0]);

    plot.setAttribute(
      "aria-label",
      `${weaponName(active)} rating from ${fmtDate(first.date)} to ${fmtDate(last.date)}: ` +
        `${Math.round(first.post)} to ${Math.round(last.post)}, peak ${Math.round(peak.post)}.`
    );
    note.textContent =
      `${points.length} rated competition${points.length === 1 ? "" : "s"} · ` +
      `peak ${fmtNum(peak.post, 0)} (${fmtDate(peak.date)}) · latest ${fmtNum(last.post, 0)}`;

    tableWrap.replaceChildren(
      el("summary", { text: "Show as a table" }),
      el("div", { class: "table-scroll" }, [
        el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: "Date" }),
              el("th", { class: "num", text: "Rating before" }),
              el("th", { class: "num", text: "Rating after" }),
              el("th", { class: "num", text: "Change" }),
            ]),
          ]),
          el("tbody", {}, [...points].reverse().map((p) =>
            el("tr", {}, [
              el("td", { text: fmtDate(p.date) }),
              el("td", { class: "num", text: fmtNum(p.pre, 0) }),
              el("td", { class: "num", text: fmtNum(p.post, 0) }),
              el("td", { class: "num", text: `${p.post - p.pre >= 0 ? "+" : "−"}${fmtNum(Math.abs(p.post - p.pre), 1)}` }),
            ])
          )),
        ]),
      ])
    );

    if (dispose) { dispose(); dispose = null; }
    try {
      const { renderRatingChart } = await import("../chart.js");
      dispose = await renderRatingChart(plot, points);
    } catch (err) {
      console.error(err);
      // The table view above already carries every value — the chart is the
      // enhancement, so a failed load degrades instead of breaking the page.
      plot.replaceChildren(el("p", { class: "notice", text: "Chart unavailable — see the table below." }));
      tableWrap.setAttribute("open", "");
    }
  }
  draw();

  return card;
}

const RESULT_COLUMNS = [
  ["POS", "Place", (v) => (v ? `#${v}` : "—")],
  ["PVICT", "Poule wins", (v) => fmtInt(v)],
  ["PIND", "Poule win %", (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`)],
  ["PTD", "Poule touches for", (v) => fmtNum(v, 0)],
  ["PTR", "Poule touches vs", (v) => fmtNum(v, 0)],
  ["TMVAVG", "DE wins", (v) => fmtInt(v)],
];

function resultsCard(f, get) {
  const results = [...f.results].sort((a, b) => (a.date < b.date ? 1 : -1));

  const rows = results.map((r) => {
    const place = get(r, "POS");
    return el("tr", {}, [
      el("td", { class: "small", text: seasonOf(r.date) }),
      el("td", {}, [
        el("a", { href: `#/competition/${r.competition_id}`, text: r.name || r.competition_id }),
        el("div", { class: "small muted", text: [r.city, r.country].filter(Boolean).join(", ") || "—" }),
      ]),
      el("td", { class: "small", text: fmtDate(r.date) }),
      el("td", { class: "small", text: weaponName(r.weapon) }),
      el("td", { class: "num" }, [
        el("span", { class: place === 1 ? "medal-1" : null, text: place ? `#${place}` : "—" }),
      ]),
      ...RESULT_COLUMNS.slice(1).map(([code, , fmt]) =>
        el("td", { class: "num", text: fmt(get(r, code)) })
      ),
    ]);
  });

  return el("section", { class: "card" }, [
    el("h2", { text: `Results (${fmtInt(results.length)} competitions)` }),
    el("p", { class: "small muted", text: "Every FIE competition on record, newest first. Poule metrics are blank for results-only archive entries." }),
    el("div", { class: "table-scroll" }, [
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: "Season" }),
            el("th", { text: "Competition" }),
            el("th", { text: "Date" }),
            el("th", { text: "Weapon" }),
            ...RESULT_COLUMNS.map(([, label]) => el("th", { class: "num", text: label })),
          ]),
        ]),
        el("tbody", {}, rows),
      ]),
    ]),
  ]);
}

function rivalsCard(f) {
  if (!f.top_rivals.length) return null;

  const rows = f.top_rivals.map((r) =>
    el("tr", {}, [
      el("td", {}, [fencerLink(r.id, r.name)]),
      el("td", { class: "flag", text: r.country ?? "—" }),
      el("td", { class: "num", text: fmtInt(r.bouts) }),
      el("td", { class: "num", text: `${fmtInt(r.wins)}–${fmtInt(r.losses)}` }),
      el("td", { class: "small", text: fmtDate(r.last_met) }),
      el("td", { class: "small" }, [
        el("a", { href: `#/h2h?a=${f.id}&b=${r.id}`, text: "Compare" }),
      ]),
    ])
  );

  return el("section", { class: "card" }, [
    el("h2", { text: "Most-met opponents" }),
    el("p", { class: "small muted", text: "Head-to-head record against the fencers met most often." }),
    el("div", { class: "table-scroll" }, [
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: "Opponent" }),
            el("th", { text: "Country" }),
            el("th", { class: "num", text: "Bouts" }),
            el("th", { class: "num", text: "W–L" }),
            el("th", { text: "Last met" }),
            el("th", { text: "" }),
          ]),
        ]),
        el("tbody", {}, rows),
      ]),
    ]),
  ]);
}

export async function render({ parts }) {
  const id = Number(parts[1]);
  if (!Number.isFinite(id)) throw new Error(`Not a fencer id: ${parts[1]}`);

  // `meta` carries the metric registry the result table is keyed by; a missing
  // shard is the expected case below, a missing meta.json is not.
  const meta = await getMeta();

  let fencer;
  try {
    fencer = await getFencer(id);
  } catch (err) {
    // Only fencers with >=2 competitions get a shard (see build_site.py).
    return el("div", { class: "page-head" }, [
      el("h1", { text: "Fencer not found" }),
      el("p", { class: "muted", text: `No profile for id ${id}. Profiles exist for fencers with at least two competitions.` }),
      el("p", {}, [el("a", { href: "#/search", text: "Back to search" })]),
    ]);
  }

  return el("div", {}, [
    head(fencer),
    careerCards(fencer),
    el("div", { class: "grid", style: "margin-top:1rem" }, [
      ratingCard(fencer),
      rivalsCard(fencer),
      resultsCard(fencer, metricReader(meta)),
    ]),
  ]);
}
