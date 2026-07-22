// Competition browser: client-side filtering over data/competitions/index.json
// (~550 KB, 3k rows — small enough to hold in memory and filter per keystroke).

import { POOLS, getCompetitionsIndex, levelName, poolCodeOf, weaponName } from "../data.js";
import { el, fencerLink, fmtDate, fmtInt, normalize } from "../util.js";

const MAX_RESULTS = 100;

// Index rows: {id, n: name, ci: city, co: country, d: date, w, g, l: level,
// e: entries, c: [champion_id, champion_name]} — see build_site.py.
let prepared = null;
async function preparedIndex() {
  if (!prepared) {
    const raw = await getCompetitionsIndex();
    prepared = raw.map((c) => ({
      ...c,
      pool: poolCodeOf(c.w, c.g),
      season: (c.d ?? "").slice(0, 4),
      key: normalize(`${c.n ?? ""} ${c.ci ?? ""} ${c.co ?? ""}`),
    }));
  }
  return prepared;
}

function row(c) {
  return el("tr", {}, [
    el("td", {}, [
      el("a", { href: `#/competition/${c.id}`, text: c.n || c.id }),
      el("div", { class: "small muted", text: [c.ci, c.co].filter(Boolean).join(", ") || "—" }),
    ]),
    el("td", { class: "small nowrap", text: fmtDate(c.d) }),
    el("td", { class: "small" }, [
      el("div", { text: weaponName(c.w) }),
      el("div", { class: "small muted", text: levelName(c.l) }),
    ]),
    el("td", {}, [c.c ? fencerLink(c.c[0], c.c[1], "medal-1") : "—"]),
    el("td", { class: "num", text: fmtInt(c.e) }),
  ]);
}

export async function render({ params }) {
  const index = await preparedIndex();
  const seasons = [...new Set(index.map((c) => c.season))].filter(Boolean).sort().reverse();

  let poolCode = params.get("pool") ?? "";
  let season = params.get("season") ?? "";

  const search = el("input", {
    class: "search-box", type: "search", id: "comp-search",
    placeholder: "Filter by competition, city or country — e.g. Budapest, World Championships",
    autocomplete: "off", value: params.get("q") ?? "",
  });

  const poolFilter = el(
    "div",
    { class: "pool-filter", role: "group", "aria-label": "Filter by weapon and gender" },
    [
      el("button", { type: "button", text: "All", "data-pool": "", "aria-pressed": poolCode ? "false" : "true" }),
      ...POOLS.map((p) =>
        el("button", {
          type: "button", text: p.label, "data-pool": p.code,
          "aria-pressed": p.code === poolCode ? "true" : "false",
        })
      ),
    ]
  );

  const seasonSelect = el(
    "select",
    { class: "select", id: "season-select", "aria-label": "Season" },
    [
      el("option", { value: "", text: "All seasons", selected: season === "" }),
      ...seasons.map((s) => el("option", { value: s, text: s, selected: s === season })),
    ]
  );

  const status = el("p", { class: "small muted", "aria-live": "polite" });
  const body = el("tbody");

  function run() {
    const terms = normalize(search.value).split(/\s+/).filter(Boolean);
    const hits = index.filter((c) =>
      (!poolCode || c.pool === poolCode) &&
      (!season || c.season === season) &&
      terms.every((t) => c.key.includes(t))
    );

    body.replaceChildren(...hits.slice(0, MAX_RESULTS).map(row));
    status.textContent = hits.length === 0
      ? "No competition matches those filters."
      : hits.length > MAX_RESULTS
        ? `${fmtInt(hits.length)} competitions — showing the ${MAX_RESULTS} most recent.`
        : `${fmtInt(hits.length)} competition${hits.length === 1 ? "" : "s"}.`;
  }

  search.addEventListener("input", run);
  seasonSelect.addEventListener("change", () => { season = seasonSelect.value; run(); });
  poolFilter.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    poolCode = button.dataset.pool;
    for (const b of poolFilter.querySelectorAll("button")) {
      b.setAttribute("aria-pressed", b === button ? "true" : "false");
    }
    run();
  });

  run();

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Competitions" }),
      el("p", { class: "muted", text: `Every senior individual FIE competition on record, newest first — ${fmtInt(index.length)} in all.` }),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "filter-row" }, [
        el("div", { class: "grow" }, [
          el("label", { class: "small muted", for: "comp-search", text: "Search" }),
          search,
        ]),
        el("div", {}, [
          el("label", { class: "small muted", for: "season-select", text: "Season" }),
          seasonSelect,
        ]),
      ]),
      poolFilter,
      status,
      el("div", { class: "table-scroll" }, [
        el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: "Competition" }),
              el("th", { text: "Date" }),
              el("th", { text: "Weapon" }),
              el("th", { text: "Champion" }),
              el("th", { class: "num", text: "Entries" }),
            ]),
          ]),
          body,
        ]),
      ]),
    ]),
  ]);
}
