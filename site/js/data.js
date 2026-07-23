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
export const getCompetitionsIndex = () => getJSON("data/competitions/index.json");
// Lazy, page-scoped: 2–4.5 MB per pool, fetched only by the metrics explorer.
export const getExplore = (pool) => getJSON(`data/explore/${pool}.json`);
export const getCompetition = (id) => getJSON(`data/competitions/${id}.json`);

// Pair files exist only for >=5 meetings (see build_site.py); `null` means
// "no bout-by-bout detail", not "never met" — the aggregate comes from the
// fencer shards' `h2h_all`.
export const getH2HPair = (a, b) => {
  const [lo, hi] = [Number(a), Number(b)].sort((x, y) => x - y);
  return getJSON(`data/h2h/${lo}-${hi}.json`).catch(() => null);
};

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
export const poolCodeOf = (weapon, gender) =>
  `${(weapon ?? "").toLowerCase()}${(gender ?? "").toLowerCase()}`;

// fie.org's own competition level codes. Anything unrecognised is shown as-is
// rather than hidden — the archive's older seasons use a long tail of them.
const LEVEL_NAMES = {
  CDM: "World Cup", CM: "World Championships", CHM: "World Championships",
  GP: "Grand Prix", JO: "Olympic Games", CHE: "European Championships",
  CE: "European Championships", CHZ: "Zonal Championships", CZ: "Zonal Championships",
  SAT: "Satellite", CHA: "Asian Championships", CHP: "Pan-American Championships",
  CHAF: "African Championships", CHO: "Oceania Championships", Q: "Qualifier",
};
export const levelName = (code) => LEVEL_NAMES[code] ?? code ?? "—";

// DE round codes as fie.org records them (see build_site._ROUND_PREFIXES).
// A competition can run a preliminary "A" tableau into the main "B" one, so
// "table of 64" is not unique within an event — Final/Semi-final naming is
// left to the caller, which knows where a round sits in the ordered list.
// Rounds of 2 and 4 are named rather than numbered: across all 3,092
// competitions on record a table of 2 or 4 is always the real final / semi —
// a preliminary tableau always feeds the main one well above that size.
const ROUND_NAMES = { 2: "Final", 4: "Semi-final", 8: "Quarter-final" };

export function roundLabel(code) {
  const match = /^([A-Za-z]*)(\d+)$/.exec(code ?? "");
  if (!match) return code ?? "—";
  const [, prefix, digits] = match;
  if (!prefix) return `Round ${digits}`;
  return ROUND_NAMES[digits] ?? `Table of ${digits}`;
}
