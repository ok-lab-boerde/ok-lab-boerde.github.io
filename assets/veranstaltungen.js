/* Veranstaltungen: Liste filtern (Suche, Gemeinde, Zeitraum, Sitzungen) und Orte auf der Karte. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("de-DE");
  const FARBE = "#0d4a8f";
  const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

  document.addEventListener("DOMContentLoaded", () => {
    const heute = new Date();
    const hIso = iso(heute);
    const termine = [...document.querySelectorAll("#vk-liste .vk-termin")].map((li) => ({
      li, d: li.dataset.d, e: li.dataset.e, g: li.dataset.g, ll: li.dataset.ll, s: li.dataset.s, suche: norm(li.textContent),
    }));
    const monate = [...document.querySelectorAll("#vk-liste .vk-monat")];
    // Vergangene Termine (seit dem letzten Abruf) ausblenden
    termine.forEach((t) => { if (t.e < hIso) t.alt = true; });

    const p = new URLSearchParams(location.search);
    if (p.get("g") && [...$("vk-g").options].some((o) => o.value === p.get("g"))) $("vk-g").value = p.get("g");

    let map = null, layer = null;
    if (typeof L !== "undefined") {
      map = L.map("vk-karte", { scrollWheelZoom: false, preferCanvas: true });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
      }).addTo(map);
      map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
      map.on("click focus", () => map.scrollWheelZoom.enable());
      map.setView([52.2, 11.3], 9);
      layer = L.layerGroup().addTo(map);
    }

    function zeitraum(t, z) {
      if (!z) return true;
      const von = new Date(heute); von.setHours(0, 0, 0, 0);
      let bis = new Date(von);
      if (z === "heute") bis = von;
      else if (z === "we") {
        const wt = von.getDay();                       // 0 = Sonntag
        bis.setDate(von.getDate() + (wt === 0 ? 0 : 7 - wt));
        if (wt >= 1 && wt <= 4) von.setDate(von.getDate() + (5 - wt));
      }
      else bis.setDate(von.getDate() + Number(z));
      return t.d <= iso(bis) && t.e >= iso(von);
    }

    function anwenden(zoomen) {
      const q = norm($("vk-q").value.trim()), g = $("vk-g").value, z = $("vk-z").value, s = $("vk-s").checked;
      const sel = termine.filter((t) => !t.alt && (!q || t.suche.includes(q)) && (!g || t.g === g) && zeitraum(t, z) && (s || t.s !== "sitzung"));
      const ids = new Set(sel);
      termine.forEach((t) => { t.li.hidden = !ids.has(t); });
      monate.forEach((m) => { m.hidden = !sel.some((t) => t.d.slice(0, 7) === m.dataset.m); });
      $("vk-treffer").textContent = `${nf.format(sel.length)} ${sel.length === 1 ? "Termin" : "Termine"}`;
      if (map) {
        layer.clearLayers();
        const orte = new Map();
        sel.forEach((t) => { if (t.ll && t.ll !== ",") orte.set(t.ll, (orte.get(t.ll) || []).concat(t)); });
        const pts = [];
        orte.forEach((liste, ll) => {
          const [lat, lon] = ll.split(",").map(Number);
          pts.push([lat, lon]);
          const m = L.circleMarker([lat, lon], { radius: Math.min(6 + liste.length, 14), color: "#fff", weight: 1.5, fillColor: FARBE, fillOpacity: 0.9 });
          const box = document.createElement("div");
          liste.slice(0, 6).forEach((t) => {
            const a = t.li.querySelector("h3 a"), zt = t.li.querySelector("time");
            const zeile = document.createElement("div");
            const b = document.createElement("strong"); b.textContent = zt.textContent.split(",").slice(0, 2).join(",");
            const l = document.createElement("a"); l.href = a.href; l.textContent = a.textContent; l.rel = "noopener";
            zeile.append(b, document.createElement("br"), l);
            zeile.style.marginBottom = "6px";
            box.append(zeile);
          });
          if (liste.length > 6) { const w = document.createElement("div"); w.textContent = `… und ${liste.length - 6} weitere`; box.append(w); }
          m.bindPopup(box, { maxWidth: 260 });
          layer.addLayer(m);
        });
        if (pts.length && zoomen) map.fitBounds(L.latLngBounds(pts), { padding: [24, 24], maxZoom: 13 });
      }
    }

    $("vk-filter").addEventListener("input", () => anwenden(true));
    $("vk-filter").addEventListener("submit", (ev) => ev.preventDefault());
    anwenden(true);
  });
})();
