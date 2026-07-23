// Compare: several fencers' metrics side by side — the multi-fencer form of
// the profile's metric chart, and where the explorer's selection and the
// profile's "compare with" both land.
//
// Everything is computed from the fencers' own shards by `metricview.js`; this
// view owns only the fencer list and keeps it, and the filters, in the URL so
// a comparison is linkable.

import { getFencer, getMeta } from "../data.js";
import { metricParams, metricSection, metricState } from "../metricview.js";
import { fencerPicker, fencerSearchIndex } from "../picker.js";
import { el, fencerHref, fmtInt } from "../util.js";

// One categorical colour slot per fencer, and no more (see chart.js) — past
// six lines the chart stops being readable anyway.
const MAX_FENCERS = 6;

const parseIds = (raw) => [...new Set(
  (raw ?? "").split(",").map((s) => Number(s.trim())).filter((n) => Number.isFinite(n) && n > 0)
)];

export async function render({ params }) {
  const meta = await getMeta();
  const wanted = parseIds(params.get("ids"));
  const overflow = Math.max(0, wanted.length - MAX_FENCERS);
  const ids = wanted.slice(0, MAX_FENCERS);
  const state = metricState(meta, params);

  // A fencer with fewer than two competitions has no shard; drop them from the
  // comparison rather than failing the whole page.
  const loaded = await Promise.all(ids.map((id) => getFencer(id).catch(() => null)));
  const fencers = loaded.filter(Boolean);
  const missing = ids.filter((id, i) => !loaded[i]);

  const hashFor = (nextIds, nextState = state) => {
    const q = metricParams(nextState, meta);
    q.set("ids", nextIds.join(","));
    return `#/compare?${q}`;
  };
  const go = (nextIds) => { location.hash = hashFor(nextIds); };

  const syncUrl = () => {
    // replaceState: the filters are the view the reader is already looking at,
    // so changing one must not push a history entry or re-route the page.
    history.replaceState(null, "", hashFor(fencers.map((f) => f.id)));
  };

  const picked = el("div", { class: "selection-bar" }, [
    fencers.length
      ? el("span", { class: "small muted", text: `Comparing ${fmtInt(fencers.length)}:` })
      : el("span", { class: "small muted", text: "No fencer picked yet." }),
    ...fencers.map((f) => el("span", { class: "tag pick-tag" }, [
      el("a", { href: fencerHref(f.id), text: f.name }),
      el("button", {
        type: "button", class: "pick-drop", "data-drop": f.id,
        "aria-label": `Remove ${f.name}`,
      }, ["×"]),
    ])),
  ]);
  picked.addEventListener("click", (ev) => {
    const button = ev.target.closest("button.pick-drop");
    if (!button) return;
    go(fencers.map((f) => f.id).filter((id) => id !== Number(button.dataset.drop)));
  });

  const controls = el("section", { class: "card" }, [
    el("h2", { text: "Fencers" }),
    picked,
  ]);

  if (fencers.length < MAX_FENCERS) {
    try {
      const index = await fencerSearchIndex();
      const chosen = new Set(fencers.map((f) => f.id));
      controls.append(fencerPicker({
        label: "Add a fencer",
        id: "compare-add",
        index: index.filter((e) => !chosen.has(e.i)),
        onPick: (id) => go([...fencers.map((f) => f.id), id]),
      }));
    } catch (err) {
      console.error(err);
      controls.append(el("p", { class: "notice", text: "The fencer index could not be loaded." }));
    }
  } else {
    controls.append(el("p", { class: "small muted", text: `Up to ${MAX_FENCERS} fencers can be compared at once — remove one to add another.` }));
  }

  if (missing.length) {
    controls.append(el("p", { class: "small muted", text: `No profile for ${missing.map((id) => `#${id}`).join(", ")} — profiles exist for fencers with at least two competitions.` }));
  }
  if (overflow) {
    controls.append(el("p", { class: "small muted", text: `${overflow} more fencer${overflow === 1 ? " was" : "s were"} dropped from the link: at most ${MAX_FENCERS} fit on one chart.` }));
  }

  const body = fencers.length
    ? metricSection({ meta, fencers, state, onChange: syncUrl, title: "Metric over time" }).node
    : el("p", { class: "notice", text: "Add a fencer to start a comparison, or pick several in the metrics explorer." });

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Compare fencers" }),
      el("p", { class: "muted" }, [
        "The same competition metrics as the explorer, plotted over time and set side by side. ",
        el("a", { href: "#/methodology?s=glossary", text: "What each metric means →" }),
      ]),
    ]),
    controls,
    body,
  ]);
}
