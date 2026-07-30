// Entry point: theme toggle, hash router, footer meta.
//
// Routes:  #/  ·  #/search?q=…&pool=…  ·  #/fencer/{id}  ·  #/h2h?a=…&b=…
//          #/competitions?pool=…&season=…  ·  #/competition/{id}
//          #/explore?pool=…&…  ·  #/compare?ids=…  ·  #/paths?pool=…&…
//          #/methodology?s=…  ·  #/play
// Views are lazily imported so a cold visit to a fencer profile doesn't parse
// the home page's code (and vice versa).

import { getMeta } from "./data.js";
import { el, errorBox, fmtInt, loading } from "./util.js";

const main = document.getElementById("main");

// ---- theme -----------------------------------------------------------------

const STORAGE_KEY = "ffs-theme";
const stored = localStorage.getItem(STORAGE_KEY);
if (stored === "light" || stored === "dark") document.documentElement.dataset.theme = stored;

document.getElementById("theme-toggle").addEventListener("click", () => {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const current = document.documentElement.dataset.theme || (prefersDark ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem(STORAGE_KEY, next);
  window.dispatchEvent(new CustomEvent("ffs:themechange", { detail: { theme: next } }));
});

// ---- routing ---------------------------------------------------------------

function parseHash() {
  const raw = location.hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  return { parts, params: new URLSearchParams(query) };
}

function setActiveNav(name) {
  for (const link of document.querySelectorAll(".site-nav a")) {
    if (link.dataset.nav === name) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

let renderToken = 0;

async function route() {
  const token = ++renderToken;
  const { parts, params } = parseHash();
  main.replaceChildren(loading());

  try {
    let view;
    if (parts.length === 0) {
      setActiveNav("home");
      view = await import("./views/home.js");
    } else if (parts[0] === "search") {
      setActiveNav("search");
      view = await import("./views/search.js");
    } else if (parts[0] === "fencer" && parts[1]) {
      setActiveNav("search");
      view = await import("./views/fencer.js");
    } else if (parts[0] === "explore") {
      setActiveNav("explore");
      view = await import("./views/explore.js");
    } else if (parts[0] === "compare") {
      setActiveNav("explore");
      view = await import("./views/compare.js");
    } else if (parts[0] === "paths") {
      setActiveNav("paths");
      view = await import("./views/paths.js");
    } else if (parts[0] === "h2h") {
      setActiveNav("h2h");
      view = await import("./views/h2h.js");
    } else if (parts[0] === "competitions") {
      setActiveNav("competitions");
      view = await import("./views/competitions.js");
    } else if (parts[0] === "competition" && parts[1]) {
      setActiveNav("competitions");
      view = await import("./views/competition.js");
    } else if (parts[0] === "methodology") {
      setActiveNav("methodology");
      view = await import("./views/methodology.js");
    } else if (parts[0] === "play") {
      setActiveNav("play");
      view = await import("./views/play.js");
    } else {
      setActiveNav(null);
      main.replaceChildren(notFound());
      return;
    }

    const node = await view.render({ parts, params });
    if (token !== renderToken) return; // a newer navigation won
    main.replaceChildren(node);
    // Hash navigation doesn't scroll on its own once the view is swapped in.
    window.scrollTo(0, 0);
  } catch (err) {
    if (token !== renderToken) return;
    console.error(err);
    main.replaceChildren(errorBox(err));
  }
}

function notFound() {
  return el("div", { class: "page-head" }, [
    el("h1", { text: "Page not found" }),
    el("p", {}, [el("a", { href: "#/", text: "Back to the home page" })]),
  ]);
}

window.addEventListener("hashchange", route);
route();

// ---- footer meta -----------------------------------------------------------

getMeta().then((meta) => {
  document.getElementById("footer-meta").textContent =
    `${fmtInt(meta.n_competitions)} competitions · ${fmtInt(meta.n_athletes)} fencers · ` +
    `${fmtInt(meta.n_bouts)} bouts · seasons ${meta.season_min}–${meta.season_max}. ` +
    `Built ${meta.generated_at.slice(0, 10)}.`;
}).catch((err) => console.error("meta:", err));
