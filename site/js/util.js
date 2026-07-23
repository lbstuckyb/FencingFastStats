// Small DOM + formatting helpers shared by the views.

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const fmtInt = (n) =>
  n === null || n === undefined || Number.isNaN(n) ? "—" : Number(n).toLocaleString("en-US");

export function fmtNum(n, digits = 1) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export const seasonOf = (iso) => (iso ? iso.slice(0, 4) : "—");

// Names in the index are stored uppercase-surname-first ("KANO Koki"); fold
// accents so "Szilagyi" matches "Szilágyi" either way round.
export const normalize = (s) =>
  (s ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

export const fencerHref = (id) => `#/fencer/${id}`;

export function fencerLink(id, name, extraClass) {
  return el("a", { href: fencerHref(id), class: extraClass }, [name || `#${id}`]);
}

// ---- small controls --------------------------------------------------------
// Toggle chips: a row of `aria-pressed` buttons carrying their value in
// `data-value`. The caller owns the state and listens on the row.

export function chipRow(label, items) {
  return el("div", { class: "pool-filter", role: "group", "aria-label": label },
    items.map((item) => el("button", {
      type: "button", text: item.label, title: item.title ?? null,
      "data-value": item.value, "aria-pressed": item.on ? "true" : "false",
    })));
}

export function pressOnly(container, active) {
  for (const b of container.querySelectorAll("button")) {
    b.setAttribute("aria-pressed", b === active ? "true" : "false");
  }
}

export function toggle(set, value) {
  if (set.has(value)) set.delete(value);
  else set.add(value);
}

export function loading(message = "Loading…") {
  return el("p", { class: "notice", text: message });
}

export function errorBox(err) {
  return el("div", { class: "notice error" }, [
    el("p", { text: "Could not load this data." }),
    el("p", { class: "small", text: String(err && err.message ? err.message : err) }),
  ]);
}
