// Competition detail: final ranking, poule grids and the direct-elimination
// tableau, from data/competitions/{id}.json.

import { genderName, getCompetition, levelName, roundLabel, weaponName } from "../data.js";
import { el, fencerLink, fmtDate, fmtInt, fmtNum } from "../util.js";

// Shown before the "show all" toggle. Deliberately short: the podium already
// covers the top four, and a 200-row ranking otherwise buries the poules and
// the tableau below a screen-and-a-half of scrolling.
const RANKING_PAGE = 16;

const nameOf = (comp, id) => comp.athletes[String(id)]?.[0] ?? (id == null ? "—" : `#${id}`);
const countryOf = (comp, id) => comp.athletes[String(id)]?.[1] ?? "";

function head(comp) {
  const bits = [
    `${weaponName(comp.weapon)} · ${genderName(comp.gender)}`,
    levelName(comp.level),
    [comp.city, comp.country].filter(Boolean).join(", "),
    fmtDate(comp.date),
  ].filter(Boolean);

  return el("div", { class: "page-head" }, [
    el("h1", { text: comp.name || comp.id }),
    el("p", { class: "muted", text: bits.join(" · ") }),
    el("p", { class: "small muted", text: [
      `${fmtInt(comp.n_entries)} entr${comp.n_entries === 1 ? "y" : "ies"}`,
      `${comp.poules.length} poule${comp.poules.length === 1 ? "" : "s"}`,
      `${comp.de.length} tableau round${comp.de.length === 1 ? "" : "s"}`,
    ].join(" · ") }),
  ]);
}

function podium(comp) {
  const top = comp.results.filter((r) => r.r && r.r <= 3).sort((a, b) => a.r - b.r);
  if (!top.length) return null;
  return el(
    "div",
    { class: "podium" },
    top.map((r) =>
      el("div", { class: `podium-slot podium-${r.r}` }, [
        el("span", { class: "small muted", text: r.r === 1 ? "Champion" : r.r === 2 ? "Runner-up" : "Third" }),
        el("div", {}, [fencerLink(r.a, nameOf(comp, r.a))]),
        el("span", { class: "small muted", text: countryOf(comp, r.a) }),
      ])
    )
  );
}

function rankingCard(comp) {
  if (!comp.results.length) {
    return el("section", { class: "card" }, [
      el("h2", { text: "Final ranking" }),
      el("p", { class: "notice", text: "fie.org's archive has no ranking recorded for this competition." }),
    ]);
  }

  const body = el("tbody");
  let expanded = false;
  const toggle = el("button", { class: "link-button", type: "button" });

  function fill() {
    const rows = expanded ? comp.results : comp.results.slice(0, RANKING_PAGE);
    body.replaceChildren(
      ...rows.map((r) =>
        el("tr", {}, [
          el("td", { class: "rank" }, [
            el("span", { class: r.r === 1 ? "medal-1" : null, text: r.r ? `${r.r}` : "—" }),
          ]),
          el("td", {}, [fencerLink(r.a, nameOf(comp, r.a))]),
          el("td", { class: "flag", text: countryOf(comp, r.a) || "—" }),
          el("td", { class: "num", text: r.s ? fmtInt(r.s) : "—" }),
          el("td", { class: "num", text: r.p === null || r.p === undefined ? "—" : fmtNum(r.p, 2) }),
        ])
      )
    );
    toggle.textContent = expanded
      ? `Show the top ${RANKING_PAGE} only`
      : `Show all ${fmtInt(comp.results.length)} entries`;
  }
  toggle.addEventListener("click", () => { expanded = !expanded; fill(); });
  fill();

  return el("section", { class: "card" }, [
    el("h2", { text: "Final ranking" }),
    el("div", { class: "table-scroll" }, [
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { class: "rank", text: "#" }),
            el("th", { text: "Fencer" }),
            el("th", { text: "Country" }),
            el("th", { class: "num", text: "Seed" }),
            el("th", { class: "num", text: "Points" }),
          ]),
        ]),
        body,
      ]),
    ]),
    comp.results.length > RANKING_PAGE ? toggle : null,
  ]);
}

// ---- poules ----------------------------------------------------------------

function pouleTable(comp, poule) {
  const n = poule.fencers.length;
  const cells = Array.from({ length: n }, () => new Array(n).fill(null));
  const tally = poule.fencers.map(() => ({ v: 0, m: 0, td: 0, tr: 0 }));

  for (const [a, b, sa, sb, status, winner] of poule.bouts) {
    cells[a][b] = { score: sa, against: sb, status, won: winner === a };
    cells[b][a] = { score: sb, against: sa, status, won: winner === b };
    if (status !== "ok") continue;
    for (const [self, other, mine, theirs] of [[a, b, sa, sb], [b, a, sb, sa]]) {
      tally[self].m += 1;
      tally[self].td += mine ?? 0;
      tally[self].tr += theirs ?? 0;
      if (winner === self) tally[self].v += 1;
    }
  }

  const rows = poule.fencers.map((id, i) =>
    el("tr", {}, [
      el("td", { class: "rank", text: i + 1 }),
      el("td", { class: "nowrap" }, [
        fencerLink(id, nameOf(comp, id)),
        el("span", { class: "flag", text: ` ${countryOf(comp, id)}` }),
      ]),
      ...poule.fencers.map((_, j) => {
        if (i === j) return el("td", { class: "grid-cell grid-self", text: "" });
        const cell = cells[i][j];
        if (!cell) return el("td", { class: "grid-cell muted", text: "·" });
        if (cell.status !== "ok") {
          return el("td", {
            class: `grid-cell ${cell.won ? "win" : ""}`,
            title: "Forfeit or no-show — excluded from the totals",
            text: cell.won ? "V*" : "D*",
          });
        }
        return el("td", {
          class: `grid-cell ${cell.won ? "win" : ""}`,
          text: `${cell.won ? "V" : ""}${cell.score ?? "—"}`,
        });
      }),
      el("td", { class: "num", text: `${tally[i].v}/${tally[i].m}` }),
      el("td", { class: "num", text: fmtInt(tally[i].td) }),
      el("td", { class: "num", text: fmtInt(tally[i].tr) }),
      el("td", { class: "num", text: `${tally[i].td - tally[i].tr > 0 ? "+" : ""}${tally[i].td - tally[i].tr}` }),
    ])
  );

  return el("div", { class: "poule" }, [
    el("h3", { text: `Poule ${poule.no}` }),
    el("div", { class: "table-scroll" }, [
      el("table", { class: "poule-grid" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { class: "rank", text: "#" }),
            el("th", { text: "Fencer" }),
            ...poule.fencers.map((_, j) => el("th", { class: "num", text: j + 1 })),
            el("th", { class: "num", text: "V/M" }),
            el("th", { class: "num", text: "TD" }),
            el("th", { class: "num", text: "TR" }),
            el("th", { class: "num", text: "Ind" }),
          ]),
        ]),
        el("tbody", {}, rows),
      ]),
    ]),
  ]);
}

function poulesCard(comp) {
  if (!comp.poules.length) {
    return el("section", { class: "card" }, [
      el("h2", { text: "Poules" }),
      el("p", { class: "notice", text: "No poule bouts in fie.org's archive for this competition — older seasons often record the final ranking only." }),
    ]);
  }

  const poules = [...comp.poules].sort((a, b) => a.no - b.no);
  return el("section", { class: "card" }, [
    el("h2", { text: `Poules (${poules.length})` }),
    el("p", { class: "small muted", text: "Each cell is the row fencer's score against the column fencer; V marks the win. Ind is TD − TR. Forfeits (*) are excluded from the totals, as they are everywhere else on this site." }),
    el("div", { class: "poule-list" }, poules.map((p) => pouleTable(comp, p))),
  ]);
}

// ---- tableau ---------------------------------------------------------------

/** fie.org's round codes aren't unique within an event (a preliminary "A"
 *  tableau can feed the main "B" one), so the closing rounds are named from
 *  their position and size instead of from the code. */
function roundTitles(rounds) {
  const titles = rounds.map((r) => roundLabel(r.round));
  const tail = { 1: "Final", 2: "Semi-finals", 4: "Quarter-finals" };
  const prefixOf = (code) => /^[A-Za-z]*/.exec(code ?? "")[0];
  const finalPrefix = prefixOf(rounds[rounds.length - 1]?.round);

  for (let i = rounds.length - 1; i >= 0; i--) {
    const name = tail[rounds[i].bouts.length];
    // Stay inside the tableau that actually produced the final — a
    // preliminary round of the same size is not a semi-final.
    if (!name || prefixOf(rounds[i].round) !== finalPrefix) break;
    titles[i] = name;
  }
  return titles;
}

function boutCard(comp, [a, b, sa, sb, winner, status]) {
  if (status === "bye" || b === null || b === undefined) {
    return el("div", { class: "de-bout bye" }, [
      el("div", { class: "de-side winner" }, [fencerLink(a, nameOf(comp, a))]),
      el("div", { class: "small muted", text: "bye" }),
    ]);
  }
  const side = (id, score) =>
    el("div", { class: `de-side ${winner === id ? "winner" : ""}` }, [
      fencerLink(id, nameOf(comp, id)),
      el("span", { class: "de-score", text: score === null || score === undefined ? "—" : String(score) }),
    ]);
  return el("div", { class: "de-bout" }, [
    side(a, sa),
    side(b, sb),
    status === "forfeit" ? el("div", { class: "small muted", text: "forfeit" }) : null,
  ]);
}

function tableauCard(comp) {
  if (!comp.de.length) {
    return el("section", { class: "card" }, [
      el("h2", { text: "Direct elimination" }),
      el("p", { class: "notice", text: "No tableau bouts in fie.org's archive for this competition." }),
    ]);
  }

  const titles = roundTitles(comp.de);
  return el("section", { class: "card" }, [
    el("h2", { text: "Direct elimination" }),
    el("p", { class: "small muted", text: "Rounds run left to right, earliest first. Long rounds scroll inside their column." }),
    el("div", { class: "bracket" }, comp.de.map((round, i) =>
      el("div", { class: "bracket-col" }, [
        el("div", { class: "bracket-head" }, [
          el("strong", { text: titles[i] }),
          el("span", { class: "small muted", text: `${round.round} · ${round.bouts.length} bout${round.bouts.length === 1 ? "" : "s"}` }),
        ]),
        el("div", { class: "bracket-bouts" }, round.bouts.map((b) => boutCard(comp, b))),
      ])
    )),
  ]);
}

export async function render({ parts }) {
  const id = parts[1];

  let comp;
  try {
    comp = await getCompetition(id);
  } catch (err) {
    return el("div", { class: "page-head" }, [
      el("h1", { text: "Competition not found" }),
      el("p", { class: "muted", text: `No competition with id ${id}.` }),
      el("p", {}, [el("a", { href: "#/competitions", text: "Browse all competitions" })]),
    ]);
  }

  return el("div", {}, [
    head(comp),
    podium(comp),
    el("div", { class: "grid", style: "margin-top:1rem" }, [
      rankingCard(comp),
      poulesCard(comp),
      tableauCard(comp),
    ]),
  ]);
}
