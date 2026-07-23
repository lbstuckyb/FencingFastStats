// Methodology: how the numbers on this site are produced. A reader-facing
// summary of docs/methodology.md, which stays the authoritative version
// (together with the docstrings in src/ffs/*.py it describes).
//
// Other views deep-link into a section with `#/methodology?s={id}` — the
// rating card on a profile, and the explorer's "what each metric means".

import { getMeta } from "../data.js";
import { el, fmtInt } from "../util.js";

function section(id, title, children) {
  return el("section", { class: "card prose", id: `s-${id}` }, [el("h2", { text: title }), ...children]);
}

function p(text) {
  return el("p", { text });
}

// The metric glossary is generated from meta.json's registry (src/ffs/metrics.py),
// so a metric can never be documented here and computed differently there.
function glossary(meta) {
  const groups = meta?.groups ?? [];
  const metrics = meta?.metrics ?? [];
  if (!metrics.length) {
    return [p("The metric glossary could not be loaded.")];
  }
  return groups.flatMap((group) => {
    const rows = metrics.filter((m) => m.group === group.code);
    if (!rows.length) return [];
    return [
      el("h3", { text: group.label }),
      el("div", { class: "table-scroll" }, [
        el("table", {}, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "Metric" }),
            el("th", { text: "Name" }),
            el("th", { text: "Definition" }),
          ])]),
          el("tbody", {}, rows.map((m) =>
            el("tr", {}, [
              el("td", { class: "nowrap" }, [el("code", { text: m.code })]),
              el("td", { class: "small nowrap", text: m.label }),
              el("td", { class: "small", text: `${m.blurb} ${m.agg === "sum" ? "Totalled" : "Averaged"} over the competitions in view.` }),
            ])
          )),
        ]),
      ]),
    ];
  });
}

export async function render({ params }) {
  const meta = await getMeta().catch(() => null);

  const page = el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Methodology" }),
      el("p", { class: "muted", text: "Where the data comes from, how every number is computed, and what it doesn't cover." }),
    ]),
    el("div", { class: "grid" }, [
      section("source", "Data source", [
        p(
          meta
            ? `Every figure on this site is derived from fie.org's own public competition archive: ${fmtInt(meta.n_competitions)} senior individual competitions from ${meta.season_min} to ${meta.season_max}, ${fmtInt(meta.n_athletes)} fencers and ${fmtInt(meta.n_bouts)} individual bouts.`
            : "Every figure on this site is derived from fie.org's own public competition archive of senior individual competitions."
        ),
        p("The FIE publishes results but no analytics layer. This project scrapes the pages' embedded result payloads, parses them into four canonical tables (competitions, athletes, results, bouts), and computes everything else offline. The site itself is static: pre-built JSON files and no server."),
        p("Scraping is throttled to at most one request every 1.5 seconds and every response is cached, so nothing is re-fetched. fie.org's robots.txt allows all crawling, including its API paths. These are unofficial figures computed by this project — they are not FIE rankings."),
      ]),
      section("bouts", "Bouts that count", [
        p("A bout is recorded as fenced (“ok”), a forfeit, or a bye. Only fenced bouts feed any statistic or rating. Forfeits — withdrawals, injuries, and poule no-shows, which the archive stores as a 0–0 result with a winner — are kept for the record but excluded from every touch, victory and rating calculation."),
        p("Coverage thins going back in time: from roughly 2016 onward the archive holds every poule and tableau bout, while many earlier competitions have only a final ranking. Those competitions still appear here, with their poule and tableau sections empty and their per-bout metrics blank rather than zero."),
      ]),
      section("rating", "The rating — and what it is not", [
        el("p", { class: "callout" }, [
          el("strong", { text: "This is not an FIE ranking." }),
          " The FIE's official ranking points are not part of this dataset and were never scraped. Every rating on this site is an Elo score computed here, from bout results alone. The legacy version of this project did show an official FIE ranking, read from a separately maintained spreadsheet; this rebuild deliberately does not, because there is no public archive of it to derive one from.",
        ]),
        p("Elo is a rating for the strength of results against the strength of opposition: beating a higher-rated fencer gains more than beating a lower-rated one, and losing to a lower-rated fencer costs more. After each bout both fencers' ratings move by K × (result − expected result), where the expected result is 1 / (1 + 10^((opponent − fencer) / 400))."),
        el("ul", {}, [
          el("li", { text: "Ratings are computed separately for each weapon and gender: a fencer's épée and foil ratings are independent scales and are never merged." }),
          el("li", { text: "Everyone starts at 1500." }),
          el("li", { text: "K = 16 for poule bouts, K = 32 for direct-elimination bouts — a knockout bout moves the rating more." }),
          el("li", { text: "K is doubled for a fencer's first 30 rated bouts in a pool, so newcomers converge on their level quickly instead of spending years climbing from 1500." }),
          el("li", { text: "Only fenced bouts count: byes and forfeits carry no result to rate on." }),
          el("li", { text: "No margin-of-victory bonus and no inactivity decay: a rating is simply where a fencer's results left them, and a flat stretch on a rating chart is a break from the international circuit, not a run of draws." }),
          el("li", { text: "Bouts are processed competition by competition in date order, poules before the tableau, largest tableau round first. Within one round fie.org's archive records no true chronology, so the order there is deterministic rather than real — a documented simplification that moves individual ratings slightly." }),
        ]),
        p("Because ratings can only be computed where bout data exists, a fencer's rating history effectively starts in the mid-2010s even when their results go back further. Fencers whose careers ended before then are rated only on whatever bouts the archive kept."),
      ]),
      section("glossary", "Competition metrics", [
        p("One row per fencer per competition, computed from bout-level data. These are the columns of the metrics explorer, and the definitions come from the same registry the numbers are computed with."),
        ...glossary(meta),
        p("A mean is always taken over the competitions that actually carry that metric, never over every competition entered: pre-2016 events usually have no poule or tableau bouts on record, so a fencer's poule averages can rest on far fewer competitions than their placings do."),
        p("These reproduce a legacy hand-built dataset of 286 competitions; the two agree on 99.3% of the 45,848 fencer-rows they share. The residual disagreements trace to genuine gaps in fie.org's archive — individual poule bouts that were never recorded — rather than to differing definitions."),
      ]),
      section("h2h", "Head-to-head", [
        p("Two fencers' record covers every recorded meeting in senior individual competition, poules and tableau alike, within a weapon. Bout-by-bout detail is generated for pairs who have met at least five times; the overall record is available for any pair."),
      ]),
      section("cohorts", "Career trajectories and cohorts", [
        p("The trajectories page plots a metric against a fencer's age: for every age, the median across a cohort of fencers, with a band covering the middle half of them (the 25th to the 75th percentile). The mean is in the tooltip and the table, but the median and the band are what the chart draws — a single mean cannot show how wide the path to the top actually is."),
        el("p", { class: "callout" }, [
          el("strong", { text: "A cohort is defined by this site's own rating, not by an FIE ranking." }),
          " The “top 10” cohort is every fencer whose peak FencingFastStats rating ever placed them in the top 10 of their weapon-and-gender pool. Since the FIE's official points are not part of this dataset, there is no official ranking here to draw a cohort from.",
        ]),
        el("ul", {}, [
          el("li", { text: "Age is the calendar year of the competition minus the fencer's birth year, so one age covers one calendar year of results rather than a season." }),
          el("li", { text: "One value per fencer per age goes into the distribution, so a fencer who entered twenty competitions that year counts once, exactly like one who entered three." }),
          el("li", { text: "Ages with fewer than three fencers on record are left out rather than drawn as the spike of a single career." }),
          el("li", { text: "A fencer's own curve reflects only the competitions fie.org's archive holds for them: a gap in the archive reads as a gap in the career." }),
        ]),
      ]),
      section("limits", "Known limits", [
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

  // The router swaps the view in and scrolls to the top, so a deep link can
  // only be honoured once that has happened.
  const wanted = params?.get("s");
  if (wanted) {
    requestAnimationFrame(() => page.querySelector(`#s-${CSS.escape(wanted)}`)?.scrollIntoView());
  }

  return page;
}
