// Home: pool selector + ELO top-20, recent competitions, titles/podiums
// leaderboards for the selected (weapon, gender) pool.

import { DEFAULT_POOL, POOLS, getMeta, getSummary, isPool, poolLabel } from "../data.js";
import { el, fencerLink, fmtDate, fmtInt, fmtNum } from "../util.js";

const TOP_N = 20;
const LEADERBOARD_N = 10;

function poolFilter(active) {
  return el(
    "div",
    { class: "pool-filter", role: "group", "aria-label": "Weapon and gender" },
    POOLS.map((p) =>
      el("button", {
        type: "button",
        text: p.label,
        "aria-pressed": p.code === active ? "true" : "false",
        "data-pool": p.code,
      })
    )
  );
}

function eloCard(summary) {
  const rows = summary.elo_top.slice(0, TOP_N).map((f, i) =>
    el("tr", {}, [
      el("td", { class: "rank", text: i + 1 }),
      el("td", {}, [fencerLink(f.id, f.name)]),
      el("td", { class: "flag", text: f.country ?? "—" }),
      el("td", { class: "num", text: fmtNum(f.rating, 0) }),
    ])
  );

  return el("section", { class: "card" }, [
    el("h2", { text: "Rating leaders" }),
    el("p", { class: "small muted", text: "Elo rating from every international bout on record." }),
    el("div", { class: "table-scroll" }, [
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { class: "rank", text: "#" }),
            el("th", { text: "Fencer" }),
            el("th", { text: "Country" }),
            el("th", { class: "num", text: "Rating" }),
          ]),
        ]),
        el("tbody", {}, rows),
      ]),
    ]),
  ]);
}

function leaderboardCard(title, note, entries, countLabel) {
  const rows = entries.slice(0, LEADERBOARD_N).map((f, i) =>
    el("tr", {}, [
      el("td", { class: "rank", text: i + 1 }),
      el("td", {}, [fencerLink(f.id, f.name)]),
      el("td", { class: "flag", text: f.country ?? "—" }),
      el("td", { class: "num", text: fmtInt(f.count) }),
    ])
  );

  return el("section", { class: "card" }, [
    el("h2", { text: title }),
    el("p", { class: "small muted", text: note }),
    el("div", { class: "table-scroll" }, [
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { class: "rank", text: "#" }),
            el("th", { text: "Fencer" }),
            el("th", { text: "Country" }),
            el("th", { class: "num", text: countLabel }),
          ]),
        ]),
        el("tbody", {}, rows),
      ]),
    ]),
  ]);
}

function recentCard(summary) {
  const rows = summary.recent_competitions.map((c) =>
    el("tr", {}, [
      el("td", {}, [
        el("a", { href: `#/competition/${c.id}`, text: c.name || c.id }),
        el("div", { class: "small muted", text: [c.city, c.country].filter(Boolean).join(", ") || "—" }),
      ]),
      el("td", { class: "small", text: fmtDate(c.date) }),
      el("td", {}, [c.champion ? fencerLink(c.champion.id, c.champion.name, "medal-1") : "—"]),
      el("td", { class: "num", text: fmtInt(c.n_entries) }),
    ])
  );

  return el("section", { class: "card" }, [
    el("h2", { text: "Recent competitions" }),
    el("p", { class: "small muted" }, [
      "Most recent events in this pool, newest first. ",
      el("a", { href: `#/competitions?pool=${summary.weapon.toLowerCase()}${summary.gender.toLowerCase()}`, text: "Browse all →" }),
    ]),
    el("div", { class: "table-scroll" }, [
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: "Competition" }),
            el("th", { text: "Date" }),
            el("th", { text: "Champion" }),
            el("th", { class: "num", text: "Entries" }),
          ]),
        ]),
        el("tbody", {}, rows),
      ]),
    ]),
  ]);
}

export async function render({ params }) {
  const requested = params.get("pool");
  const pool = isPool(requested) ? requested : DEFAULT_POOL;
  const [meta, summary] = await Promise.all([getMeta(), getSummary(pool)]);

  const filter = poolFilter(pool);
  filter.addEventListener("click", (ev) => {
    const code = ev.target.closest("button")?.dataset.pool;
    if (code) location.hash = `#/?pool=${code}`;
  });

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "International fencing, measured" }),
      el("p", { class: "muted" }, [
        `Ratings, results and rivalries from ${fmtInt(meta.n_competitions)} FIE competitions ` +
          `(${meta.season_min}–${meta.season_max}). Showing ${poolLabel(pool)}. `,
        el("a", { href: "#/search", text: "Search a fencer →" }),
      ]),
    ]),
    filter,
    el("div", { class: "grid grid-2" }, [
      eloCard(summary),
      recentCard(summary),
      leaderboardCard(
        "Most titles",
        "Competitions won on this circuit.",
        summary.leaderboards.titles ?? [],
        "Titles"
      ),
      leaderboardCard(
        "Most podiums",
        "Top-three finishes on this circuit.",
        summary.leaderboards.podiums ?? [],
        "Podiums"
      ),
    ]),
  ]);
}
