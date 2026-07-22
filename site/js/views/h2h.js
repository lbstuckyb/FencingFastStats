// Head-to-head explorer: pick two fencers, get their record and every bout
// they've fenced.
//
// The aggregate comes from the fencers' own shards (`h2h_all` covers *every*
// opponent, so "never met" is a real answer rather than a missing file); the
// bout-by-bout list comes from the pair file, which build_site.py only writes
// for pairs with >=5 meetings.

import { getFencer, getFencerIndex, getH2HPair, roundLabel, weaponName } from "../data.js";
import { el, fencerLink, fmtDate, fmtInt, normalize } from "../util.js";

const SUGGESTIONS = 8;

function picker(label, slot, index, selected, onPick) {
  const input = el("input", {
    class: "search-box", type: "search", id: `h2h-${slot}`,
    placeholder: "Type a fencer's name", autocomplete: "off",
    value: selected ? selected.n : "",
  });
  const list = el("ul", { class: "suggest" });

  function close() { list.replaceChildren(); }

  input.addEventListener("input", () => {
    const terms = normalize(input.value).split(/\s+/).filter(Boolean);
    if (!terms.length) return close();
    const hits = index.filter((e) => terms.every((t) => e.key.includes(t))).slice(0, SUGGESTIONS);
    list.replaceChildren(...hits.map((e) =>
      el("li", {}, [
        el("button", { type: "button", "data-id": e.i }, [
          el("span", { class: "name", text: e.n }),
          el("span", { class: "flag", text: e.c ?? "" }),
        ]),
      ])
    ));
  });
  input.addEventListener("blur", () => setTimeout(close, 150));
  list.addEventListener("click", (ev) => {
    const button = ev.target.closest("button");
    if (!button) return;
    close();
    onPick(Number(button.dataset.id));
  });

  return el("div", { class: "h2h-picker" }, [
    el("label", { class: "small muted", for: `h2h-${slot}`, text: label }),
    input,
    list,
  ]);
}

function recordCard(a, b, rows) {
  const bouts = rows.reduce((n, r) => n + r[2], 0);
  const winsA = rows.reduce((n, r) => n + r[3], 0);
  const winsB = bouts - winsA;
  const lastMet = rows.reduce((d, r) => (r[4] > d ? r[4] : d), "");

  return el("section", { class: "card" }, [
    el("h2", { text: "Head-to-head" }),
    el("div", { class: "h2h-score" }, [
      el("div", { class: "h2h-name" }, [
        el("div", {}, [fencerLink(a.id, a.name)]),
        el("span", { class: "small muted", text: a.country ?? "" }),
      ]),
      el("div", { class: `h2h-count ${winsA > winsB ? "lead" : ""}`, text: winsA }),
      el("div", { class: "h2h-dash", text: "–" }),
      el("div", { class: `h2h-count ${winsB > winsA ? "lead" : ""}`, text: winsB }),
      el("div", { class: "h2h-name right" }, [
        el("div", {}, [fencerLink(b.id, b.name)]),
        el("span", { class: "small muted", text: b.country ?? "" }),
      ]),
    ]),
    el("p", { class: "small muted", text: `${fmtInt(bouts)} meeting${bouts === 1 ? "" : "s"} · last met ${fmtDate(lastMet)}` }),
    rows.length > 1
      ? el("div", { class: "table-scroll" }, [
        el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: "Weapon" }),
              el("th", { class: "num", text: "Bouts" }),
              el("th", { class: "num", text: "W–L" }),
              el("th", { text: "Last met" }),
            ]),
          ]),
          el("tbody", {}, rows.map((r) =>
            el("tr", {}, [
              el("td", { text: weaponName(r[1]) }),
              el("td", { class: "num", text: fmtInt(r[2]) }),
              el("td", { class: "num", text: `${r[3]}–${r[2] - r[3]}` }),
              el("td", { class: "small", text: fmtDate(r[4]) }),
            ])
          )),
        ]),
      ])
      : null,
  ]);
}

function boutsCard(pair, a, b) {
  // The pair file is oriented on the lower athlete id, which may be either
  // of the two picked fencers — flip it onto A's perspective.
  const flip = pair.a.id !== a.id;

  const rows = pair.bouts.map((bout) => {
    const scoreA = flip ? bout.score_b : bout.score_a;
    const scoreB = flip ? bout.score_a : bout.score_b;
    const winnerIsA = bout.winner === a.id;
    return el("tr", {}, [
      el("td", { class: "small nowrap", text: fmtDate(bout.date) }),
      el("td", {}, [
        el("a", { href: `#/competition/${bout.competition_id}`, text: bout.competition || bout.competition_id }),
        el("div", { class: "small muted", text: `${weaponName(bout.weapon)} · ${bout.phase === "poule" ? "Poule" : roundLabel(bout.round)}` }),
      ]),
      el("td", { class: "num" }, [
        el("span", { class: winnerIsA ? "win" : null, text: scoreA === null || scoreA === undefined ? "—" : String(scoreA) }),
        el("span", { class: "muted", text: " – " }),
        el("span", { class: winnerIsA ? null : "win", text: scoreB === null || scoreB === undefined ? "—" : String(scoreB) }),
      ]),
      el("td", {}, [bout.winner ? fencerLink(bout.winner, bout.winner === a.id ? a.name : b.name) : "—"]),
      el("td", { class: "small muted", text: bout.status === "ok" ? "" : bout.status }),
    ]);
  });

  return el("section", { class: "card" }, [
    el("h2", { text: "Every bout" }),
    el("div", { class: "table-scroll" }, [
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: "Date" }),
            el("th", { text: "Competition" }),
            el("th", { class: "num", text: "Score" }),
            el("th", { text: "Winner" }),
            el("th", { text: "" }),
          ]),
        ]),
        el("tbody", {}, rows),
      ]),
    ]),
  ]);
}

async function comparison(idA, idB) {
  if (idA === idB) {
    return el("p", { class: "notice", text: "Pick two different fencers." });
  }

  const [a, b] = await Promise.all([getFencer(idA), getFencer(idB)]);
  const rows = (a.h2h_all ?? []).filter((r) => r[0] === idB);

  if (!rows.length) {
    return el("section", { class: "card" }, [
      el("h2", { text: "No recorded meeting" }),
      el("p", { class: "muted" }, [
        `${a.name} and ${b.name} have never met in a senior individual FIE competition on record.`,
      ]),
    ]);
  }

  const total = rows.reduce((n, r) => n + r[2], 0);
  const pair = total >= 5 ? await getH2HPair(idA, idB) : null;

  return el("div", { class: "grid" }, [
    recordCard(a, b, rows),
    pair
      ? boutsCard(pair, a, b)
      : el("p", { class: "small muted", text: "Bout-by-bout detail is generated for pairs with at least five meetings." }),
  ]);
}

export async function render({ params }) {
  const raw = await getFencerIndex();
  const index = raw.map((e) => ({ ...e, key: normalize(e.n) }));
  const byId = new Map(index.map((e) => [e.i, e]));

  const idA = Number(params.get("a")) || null;
  const idB = Number(params.get("b")) || null;

  const go = (a, b) => {
    const query = [a ? `a=${a}` : "", b ? `b=${b}` : ""].filter(Boolean).join("&");
    location.hash = `#/h2h${query ? `?${query}` : ""}`;
  };

  const pickers = el("div", { class: "h2h-pickers" }, [
    picker("Fencer A", "a", index, byId.get(idA), (id) => go(id, idB)),
    el("div", { class: "h2h-vs", text: "vs" }),
    picker("Fencer B", "b", index, byId.get(idB), (id) => go(idA, id)),
  ]);

  const body = el("div", { class: "h2h-body" });
  if (idA && idB) {
    body.replaceChildren(await comparison(idA, idB));
  } else {
    body.replaceChildren(el("p", { class: "notice", text: "Choose two fencers to see their record and every bout between them." }));
  }

  return el("div", {}, [
    el("div", { class: "page-head" }, [
      el("h1", { text: "Head-to-head" }),
      el("p", { class: "muted", text: "Every recorded meeting between two fencers, across poules and direct elimination." }),
    ]),
    el("div", { class: "card" }, [pickers]),
    body,
  ]);
}
