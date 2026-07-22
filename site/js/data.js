// Data access for the static site. Every fetch is a *relative* path so the
// site works from any base (local http.server, GitHub Pages project subpath).

const cache = new Map();

export function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(path).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${path}`);
      return r.json();
    }).catch((err) => {
      cache.delete(path); // don't cache failures — a retry should re-fetch
      throw err;
    }));
  }
  return cache.get(path);
}

export const getMeta = () => getJSON("data/meta.json");
export const getFencerIndex = () => getJSON("data/fencers/index.json");
export const getSummary = (pool) => getJSON(`data/summary/${pool}.json`);
export const getFencer = (id) => getJSON(`data/fencers/${Number(id) % 100}/${Number(id)}.json`);

// ---- pools -----------------------------------------------------------------
// Pool codes are {weapon}{gender}, e.g. "ef" = Epee / Female (see build_site.py).

export const POOLS = [
  { code: "em", label: "Men's Épée", weapon: "E", gender: "M" },
  { code: "ef", label: "Women's Épée", weapon: "E", gender: "F" },
  { code: "fm", label: "Men's Foil", weapon: "F", gender: "M" },
  { code: "ff", label: "Women's Foil", weapon: "F", gender: "F" },
  { code: "sm", label: "Men's Sabre", weapon: "S", gender: "M" },
  { code: "sf", label: "Women's Sabre", weapon: "S", gender: "F" },
];

export const DEFAULT_POOL = "em";

export const isPool = (code) => POOLS.some((p) => p.code === code);
export const poolLabel = (code) => POOLS.find((p) => p.code === code)?.label ?? code;

const WEAPON_NAMES = { E: "Épée", F: "Foil", S: "Sabre" };
export const weaponName = (w) => WEAPON_NAMES[w] ?? w ?? "—";
export const genderName = (g) => (g === "F" ? "Women" : g === "M" ? "Men" : "—");
