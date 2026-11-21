/* Abschnitt „Veranstaltungen“ auf Orts- und Gemeindeseiten: lädt /veranstaltungen/termine.json und zeigt die nächsten Termine. */
(() => {
  "use strict";
  const TAGE = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  function wann(start, ende) {
    const d = new Date(start.slice(0, 10) + "T12:00:00");
    let s = `${TAGE[d.getDay()]}, ${d.getDate()}.${d.getMonth() + 1}.`;
    if (start.length > 10) s += ` ${start.slice(11, 16)} Uhr`;
    if (ende && ende.slice(0, 10) > start.slice(0, 10)) { const e = new Date(ende.slice(0, 10) + "T12:00:00"); s += ` bis ${e.getDate()}.${e.getMonth() + 1}.`; }
    return s;
  }
  document.addEventListener("DOMContentLoaded", async () => {
    const box = document.querySelector(".termine-box");
    if (!box) return;
    const ul = box.querySelector(".termine-liste");
    const leer = (txt) => { const li = document.createElement("li"); li.className = "leer"; li.textContent = txt; ul.replaceChildren(li); };
    let d;
    try { d = await (await fetch("/veranstaltungen/termine.json")).json(); } catch { leer("Die Termine konnten nicht geladen werden."); return; }
    const heute = iso(new Date());
    const alle = d.termine.map(([start, ende, titel, ort, g, ot, url, art]) => ({ start, ende, titel, ort, g, ot, url, art }))
      .filter((t) => t.g === box.dataset.g && (t.ende || t.start).slice(0, 10) >= heute);
    const ot = box.dataset.ot;
    let liste = ot ? alle.filter((t) => t.ot === ot) : alle;
    const hinweis = document.createElement("p"); hinweis.className = "klein";
    if (ot && !liste.length && alle.length) {
      hinweis.textContent = `Für ${box.dataset.name} sind keine Termine bekannt. Termine in der Gemeinde:`;
      liste = alle;
    }
    if (!liste.length) { leer("Zurzeit sind keine Termine bekannt."); return; }
    const lis = liste.slice(0, 8).map((t) => {
      const li = document.createElement("li");
      const z = document.createElement("span"); z.className = "zusatz"; z.textContent = wann(t.start, t.ende);
      const a = document.createElement("a"); a.href = t.url; a.rel = "noopener"; a.textContent = t.titel;
      li.append(z, " ", a);
      if (t.ort) { const o = document.createElement("span"); o.className = "zusatz"; o.textContent = ` · ${t.ort}`; li.append(o); }
      return li;
    });
    ul.replaceChildren(...lis);
    if (hinweis.textContent) ul.before(hinweis);
    if (liste.length > 8) {
      const mehr = document.createElement("li"); mehr.className = "zusatz"; mehr.textContent = `… und ${liste.length - 8} weitere`; ul.append(mehr);
    }
  });
})();
