/* Karten-Check: Betriebe nach fehlenden OSM-Angaben suchen. Daten: /betriebe/data/betriebe.json */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("de-DE");
  const SEITE = 50;
  let liste = [], namen = [], anzeigen = SEITE;
  const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");

  function filtern() {
    const q = norm($("kc-q").value.trim()), ort = $("kc-ort").value, f = $("kc-fehlt").value;
    return liste.filter((b) =>
      (!q || b.suche.includes(q)) && (ort === "" || b.gemeinde === +ort) &&
      (f === "" || (f === "voll" ? b.fehlt === 0 : (b.fehlt & (1 << +f)) !== 0)));
  }

  function zeichnen(neu = true) {
    if (neu) anzeigen = SEITE;
    const sel = filtern();
    $("kc-treffer").textContent = `${nf.format(sel.length)} ${sel.length === 1 ? "Betrieb" : "Betriebe"}`;
    const ul = $("kc-liste");
    ul.innerHTML = "";
    const frag = document.createDocumentFragment();
    sel.slice(0, anzeigen).forEach((b) => {
      const li = document.createElement("li");
      const links = document.createElement("span");
      const a = document.createElement("a");
      a.href = b.url + "#karten-check"; a.textContent = b.name;
      const info = document.createElement("span");
      info.className = "info";
      const fehlt = namen.filter((_, i) => b.fehlt & (1 << i));
      info.textContent = `${b.detail} · ${b.ort} · ` + (fehlt.length ? `fehlt: ${fehlt.join(", ")}` : "vollständig");
      links.append(a, document.createElement("br"), info);
      const [typ, id] = b.osm.split("/");
      const edit = document.createElement("a");
      edit.href = `https://www.openstreetmap.org/edit?editor=id&${typ}=${id}`;
      edit.rel = "nofollow";
      edit.textContent = "bearbeiten";
      edit.setAttribute("aria-label", `${b.name} in OpenStreetMap bearbeiten`);
      li.append(links, edit);
      frag.append(li);
    });
    ul.append(frag);
    $("kc-mehr").hidden = sel.length <= anzeigen;
    $("kc-mehr").textContent = `Weitere anzeigen (${nf.format(sel.length - Math.min(anzeigen, sel.length))})`;
  }

  document.addEventListener("DOMContentLoaded", () => {
    fetch("/betriebe/data/betriebe.json").then((r) => r.json()).then((raw) => {
      const f = Object.fromEntries(raw.felder.map((k, i) => [k, i]));
      namen = raw.check;
      liste = raw.betriebe.map((r) => ({
        name: r[f.name], detail: r[f.detail], gemeinde: r[f.gemeinde], ort: r[f.ort], url: r[f.url],
        fehlt: r[f.fehlt], osm: r[f.osm], suche: norm(`${r[f.name]} ${r[f.detail]} ${r[f.ort]}`),
      }));
      const p = new URLSearchParams(location.search);
      if (p.get("q")) $("kc-q").value = p.get("q");
      $("kc-q").addEventListener("input", () => zeichnen());
      $("kc-ort").addEventListener("change", () => zeichnen());
      $("kc-fehlt").addEventListener("change", () => zeichnen());
      $("kc-suche").addEventListener("submit", (ev) => ev.preventDefault());
      $("kc-mehr").addEventListener("click", () => { anzeigen += SEITE; zeichnen(false); });
      zeichnen();
    }).catch(() => { $("kc-treffer").textContent = "Die Daten konnten nicht geladen werden."; });
  });
})();
