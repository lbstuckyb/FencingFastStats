// Methodology: how the numbers on this site are produced. A reader-facing
// summary of docs/methodology.md, which stays the authoritative version
// (together with the docstrings in src/ffs/*.py it describes).

import { getMeta } from "../data.js";
import { el, fmtInt } from "../util.js";

const METRICS = [
  ["POS", "Final placing in the competition."],
  ["PVICT", "Poule victories."],
  ["PIND", "Poule win ratio — victories divided by poule matches fenced. (Named after FIE's “indicator”, but the legacy dataset's values are a win ratio, and this site reproduces them as such.)"],
  ["PTD / PTR", "Touches scored / received across the poules."],
  ["PT-DIFF", "Poule touch differential (PTD − PTR)."],
  ["PMTD / PMTR", "Mean touches scored / received per poule bout."],
  ["TTD / TTR", "Touches scored / received in direct elimination."],
  ["TMVAVG", "Direct-elimination victories."],
  ["Q", "Qualified from the poules into the tableau (1/0)."],
  ["PEXMPT", "Exempt from the poules — seeded straight into the tableau."],
  ["T64+ / T96+", "Reached the table of 64 / the round feeding it."],
  ["PM1V% / PM1&2V%", "Won the first poule bout / the first two, by seed order."],
];

function section(title, children) {
  return el("section", { class: "card prose" }, [el("h2", { text: title }), ...children]);
}

function p(text) {
  return el("p", { text });
}

export async function render() {
  const meta = await getMeta().catch(() => null);

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Methodology" }),
      el("p", { class: "muted", text: "Where the data comes from, how every number is computed, and what it doesn't cover." }),
    ]),
    el("div", { class: "grid" }, [
      section("Data source", [
        p(
          meta
            ? `Every figure on this site is derived from fie.org's own public competition archive: ${fmtInt(meta.n_competitions)} senior individual competitions from ${meta.season_min} to ${meta.season_max}, ${fmtInt(meta.n_athletes)} fencers and ${fmtInt(meta.n_bouts)} individual bouts.`
            : "Every figure on this site is derived from fie.org's own public competition archive of senior individual competitions."
        ),
        p("The FIE publishes results but no analytics layer. This project scrapes the pages' embedded result payloads, parses them into four canonical tables (competitions, athletes, results, bouts), and computes everything else offline. The site itself is static: pre-built JSON files and no server."),
        p("Scraping is throttled to at most one request every 1.5 seconds and every response is cached, so nothing is re-fetched. fie.org's robots.txt allows all crawling, including its API paths. These are unofficial figures computed by this project — they are not FIE rankings."),
      ]),
      section("Bouts that count", [
        p("A bout is recorded as fenced (“ok”), a forfeit, or a bye. Only fenced bouts feed any statistic or rating. Forfeits — withdrawals, injuries, and poule no-shows, which the archive stores as a 0–0 result with a winner — are kept for the record but excluded from every touch, victory and rating calculation."),
        p("Coverage thins going back in time: from roughly 2016 onward the archive holds every poule and tableau bout, while many earlier competitions have only a final ranking. Those competitions still appear here, with their poule and tableau sections empty and their per-bout metrics blank rather than zero."),
      ]),
      section("Competition metrics", [
        p("One row per fencer per competition, computed from bout-level data:"),
        el("div", { class: "table-scroll" }, [
          el("table", {}, [
            el("thead", {}, [el("tr", {}, [el("th", { text: "Metric" }), el("th", { text: "Definition" })])]),
            el("tbody", {}, METRICS.map(([name, definition]) =>
              el("tr", {}, [
                el("td", { class: "nowrap" }, [el("code", { text: name })]),
                el("td", { text: definition }),
              ])
            )),
          ]),
        ]),
        p("These reproduce a legacy hand-built dataset of 286 competitions; the two agree on 99.3% of the 45,848 fencer-rows they share. The residual disagreements trace to genuine gaps in fie.org's archive — individual poule bouts that were never recorded — rather than to differing definitions."),
      ]),
      section("Elo ratings", [
        p("Ratings are computed separately for each weapon and gender: a fencer's épée rating and foil rating are independent scales and are never merged."),
        el("ul", {}, [
          el("li", { text: "Everyone starts at 1500." }),
          el("li", { text: "K = 16 for poule bouts, K = 32 for direct-elimination bouts — a knockout bout moves the rating more." }),
          el("li", { text: "K is doubled for a fencer's first 30 rated bouts in a pool, so new fencers converge quickly." }),
          el("li", { text: "No margin-of-victory bonus and no inactivity decay in this version: a rating is simply where a fencer's results left them." }),
          el("li", { text: "Bouts are processed competition by competition in date order, poules before the tableau, and largest tableau round first. Within a round the archive has no true chronology, so the order there is deterministic rather than real." }),
        ]),
        p("A fencer's rating chart shows the rating after every competition, so a flat stretch is a break from the international circuit, not a run of draws."),
      ]),
      section("Head-to-head", [
        p("Two fencers' record covers every recorded meeting in senior individual competition, poules and tableau alike, within a weapon. Bout-by-bout detail is generated for pairs who have met at least five times; the overall record is available for any pair."),
      ]),
      section("Known limits", [
        el("ul", {}, [
          el("li", { text: "Senior individual events only — no team, junior, cadet or veteran results." }),
          el("li", { text: "Pre-2016 competitions frequently have no bout-level data, so ratings and poule metrics start later than the results do." }),
          el("li", { text: "Poule seed order is reconstructed from the archive's bout ordering, so the two “first bout” metrics are a faithful proxy rather than an exact port." }),
          el("li", { text: "Fencers with a single competition on record get no profile page, to keep the site's data small." }),
        ]),
        p("The full technical write-up, including every deviation from the legacy dataset and the validation numbers behind it, lives in docs/methodology.md in the project repository."),
      ]),
    ]),
  ]);
}
