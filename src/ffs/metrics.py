"""The competition-metric registry — one description of every metric
`stats.compute_stats` produces, shared by the Python builders and (through
`meta.json`) by every JS view, so labels, aggregation and sort direction are
defined exactly once.

`agg` and `better` are ports of the legacy Dash app's own choices: its
`update_table_ind` aggregation dict (`legacy/app/app_main.py:537` — `T64+`
and `TPRE64` summed, everything else averaged, including `POS`) and its
reversed `POS` axis in `indres-graph` (`:583`).

`den` names the *denominator* a mean has to be taken over when re-aggregating
pre-summed rows client-side (see `build_site.build_explore`). It is needed
because the metrics have genuinely different populations: pre-~2016
competitions carry no bout data at all, so a fencer's 40 results might hold 40
`POS` values but only 12 `PVICT` values and 9 `TTR` values. Averaging a sum
over the wrong count would silently under-report. Each `den` is the count of
non-null values of one representative column (`COUNT_SOURCE`); metrics
sharing a population share a counter rather than each carrying their own.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Metric:
    code: str
    """Canonical column name, as in `stats_fencer_comp.parquet`."""
    label: str
    """Full human-readable name, for pickers and tooltips."""
    short: str
    """Compact name, for table column headers."""
    group: str
    """`overall` | `poule` | `de` — drives the column-group toggles."""
    agg: str
    """`mean` | `sum` — how the metric aggregates over several competitions."""
    better: str | None
    """`low` | `high` | `None` — which direction is a better result, for
    default sort direction, axis reversal and "who won this row" marking.
    `None` means the metric is descriptive, not good-or-bad."""
    fmt: str
    """`int` | `float1` | `float2` | `pct` — display format."""
    den: str
    """Key into `COUNT_SOURCE`: which population a `mean` is taken over."""
    blurb: str
    """One-line explanation, for tooltips and the methodology glossary."""


# Which non-null count each `den` corresponds to. The representative column is
# arbitrary within its population -- e.g. `PVICT` is non-null on exactly the
# rows where any poule-bout metric is.
COUNT_SOURCE: dict[str, str] = {
    "comps": "POS",          # every result on record
    "poule": "PVICT",        # the fencer fenced poule bouts we have data for
    "pexmpt": "PEXMPT",      # the competition had poule data (exempt or not)
    "pstd": "p_tr_std",      # >=2 poule bouts, so a spread exists
    "q": "Q",                # the competition had a recorded tableau
    "qual": "TMVAVG",        # the fencer reached the tableau (Q == 1)
    "de": "TTR",             # the fencer fenced tableau bouts we have data for
    "dstd": "table_tr_std",  # >=2 tableau bouts, so a spread exists
}

METRICS: list[Metric] = [
    Metric("POS", "Final place", "Place", "overall", "mean", "low", "float1", "comps",
           "Final placing in the competition."),
    Metric("Q", "Qualified to the tableau", "Qual", "overall", "mean", "high", "pct", "q",
           "Made it out of the poules into the direct-elimination tableau; averaged, "
           "the share of entries where the fencer reached the tableau."),
    Metric("PEXMPT", "Poule exemption", "Exempt", "overall", "mean", None, "pct", "pexmpt",
           "Fenced no poule bouts and went straight into the tableau — a seeding "
           "exemption, or an archive gap where the poule was never recorded."),
    Metric("PVICT", "Poule victories", "P wins", "poule", "mean", "high", "float1", "poule",
           "Bouts won in the poules."),
    Metric("PTR", "Poule touches received", "P TR", "poule", "mean", "low", "float1", "poule",
           "Touches received across all of the fencer's poule bouts."),
    Metric("PTD", "Poule touches scored", "P TD", "poule", "mean", "high", "float1", "poule",
           "Touches scored across all of the fencer's poule bouts."),
    Metric("PIND", "Poule win ratio", "P win %", "poule", "mean", "high", "pct", "poule",
           "Poule victories divided by poule bouts fenced. (Named after FIE's "
           "“indicator”, but the legacy dataset's values are a win ratio and this "
           "site reproduces them as such.)"),
    Metric("PT-DIFF", "Poule touch differential", "P diff", "poule", "mean", "high", "float1", "poule",
           "Poule touches scored minus touches received (PTD − PTR)."),
    Metric("PMTR", "Touches received per poule bout", "P TR/bout", "poule", "mean", "low", "float2", "poule",
           "Mean touches received in a poule bout."),
    Metric("PMTD", "Touches scored per poule bout", "P TD/bout", "poule", "mean", "high", "float2", "poule",
           "Mean touches scored in a poule bout."),
    Metric("PMT-DIFF", "Touch differential per poule bout", "P diff/bout", "poule", "mean", "high", "float2", "poule",
           "Mean per-bout poule touch differential (PMTD − PMTR)."),
    Metric("p_tr_std", "Poule touches received (spread)", "P TR sd", "poule", "mean", None, "float2", "pstd",
           "Standard deviation of touches received per poule bout — how consistent "
           "the fencer's defence is from bout to bout."),
    Metric("p_td_std", "Poule touches scored (spread)", "P TD sd", "poule", "mean", None, "float2", "pstd",
           "Standard deviation of touches scored per poule bout."),
    Metric("PM1V%", "First poule bout won", "P bout 1", "poule", "mean", "high", "pct", "poule",
           "Won the first poule bout, by reconstructed seed order — how often the "
           "fencer starts the poule well."),
    Metric("PM1&2V%", "First two poule bouts won", "P bouts 1&2", "poule", "mean", "high", "pct", "poule",
           "Won both the first and the second poule bout, by reconstructed seed order."),
    Metric("TTR", "Touches received per DE bout", "DE TR", "de", "mean", "low", "float2", "de",
           "Mean touches received in a direct-elimination bout."),
    Metric("TTD", "Touches scored per DE bout", "DE TD", "de", "mean", "high", "float2", "de",
           "Mean touches scored in a direct-elimination bout."),
    Metric("TMT-DIFF", "Touch differential per DE bout", "DE diff", "de", "mean", "high", "float2", "de",
           "Mean per-bout direct-elimination touch differential (TTD − TTR)."),
    Metric("table_tr_std", "DE touches received (spread)", "DE TR sd", "de", "mean", None, "float2", "dstd",
           "Standard deviation of touches received per direct-elimination bout."),
    Metric("table_td_std", "DE touches scored (spread)", "DE TD sd", "de", "mean", None, "float2", "dstd",
           "Standard deviation of touches scored per direct-elimination bout."),
    Metric("TMVAVG", "DE victories", "DE wins", "de", "mean", "high", "float2", "qual",
           "Bouts won in the direct-elimination tableau."),
    Metric("T64+", "Reached the table of 64", "T64+", "overall", "sum", "high", "int", "comps",
           "Entries into the table of 64 (fie.org round code B64)."),
    Metric("TPRE64", "Reached the preliminary table", "TPRE64", "overall", "sum", "high", "int", "comps",
           "Entries into the preliminary tableau that feeds the table of 64 "
           "(fie.org round code A64). The legacy app called this “T96+”, which was "
           "never FIE terminology."),
]

METRIC_CODES: list[str] = [m.code for m in METRICS]
COUNT_KEYS: list[str] = list(COUNT_SOURCE)
BY_CODE: dict[str, Metric] = {m.code: m for m in METRICS}

# Series the trajectories page can plot that aren't per-competition metrics:
# they only exist once results are collapsed to one value per (athlete, age).
# Same shape as `Metric` minus the fields that make no sense off a stats row.
PATH_EXTRA_SERIES: list[dict] = [
    {"code": "rating", "label": "FencingFastStats rating", "short": "Rating",
     "better": "high", "fmt": "int",
     "blurb": "The fencer's rating at the end of that year. Computed by this site from "
              "bout results — it is not an FIE ranking."},
    {"code": "n_comps", "label": "Competitions entered in the year", "short": "Comps",
     "better": None, "fmt": "float1",
     "blurb": "How many competitions of this pool the fencer entered at that age."},
    {"code": "rate_t64", "label": "Share of entries reaching the table of 64", "short": "T64+ rate",
     "better": "high", "fmt": "pct",
     "blurb": "Entries into the table of 64 as a share of competitions entered that year."},
    {"code": "rate_tpre64", "label": "Share of entries reaching the preliminary table",
     "short": "TPRE64 rate", "better": "high", "fmt": "pct",
     "blurb": "Entries into the preliminary tableau as a share of competitions entered that year."},
    {"code": "rate_podium", "label": "Share of entries finishing on the podium", "short": "Podium rate",
     "better": "high", "fmt": "pct",
     "blurb": "Top-three finishes as a share of competitions entered that year."},
    {"code": "rate_title", "label": "Share of entries won", "short": "Title rate",
     "better": "high", "fmt": "pct",
     "blurb": "Wins as a share of competitions entered that year."},
]

GROUPS = [
    {"code": "overall", "label": "Overall"},
    {"code": "poule", "label": "Poules"},
    {"code": "de", "label": "Direct elimination"},
]


def registry_json() -> dict:
    """The registry as it is embedded in `meta.json` — `metrics` in the same
    order as every shard's metric array and every explorer row's sums."""
    return {
        "metrics": [asdict(m) for m in METRICS],
        "groups": GROUPS,
        "counts": COUNT_KEYS,
        "path_series": PATH_EXTRA_SERIES,
    }
