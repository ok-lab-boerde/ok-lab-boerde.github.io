/* Feuerwehren: Karte der Feuerwehrhäuser aus #fw-daten, Liste nach Suche und Gemeinde filtern. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("de-DE");
  const ROT = "#c62828";
  const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/ß/g, "ss");

  document.addEventListener("DOMContentLoaded", () => {
    const eintraege = [...document.querySelectorAll("#fw-liste .fw-eintrag")].map((li) => ({
      li, i: li.dataset.i, g: li.dataset.g, suche: norm(li.textContent),
    }));
    const gruppen = [...document.querySelectorAll("#fw-liste .fw-gemeinde")];
    const p = new URLSearchParams(location.search);
    if (p.get("g") && [...$("fw-g").options].some((o) => o.value === p.get("g"))) $("fw-g").value = p.get("g");

    let map = null, layer = null;
    const marker = {};
    if (typeof L !== "undefined") {
      map = L.map("fw-karte", { scrollWheelZoom: false, preferCanvas: true });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
      }).addTo(map);
      map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
      map.on("click focus", () => map.scrollWheelZoom.enable());
      map.setView([52.2, 11.35], 9);
      layer = L.layerGroup().addTo(map);
      JSON.parse($("fw-daten").textContent).forEach(([lat, lon, name, ort, i, werk]) => {
        const m = L.circleMarker([lat, lon], { radius: 7, color: "#fff", weight: 1.5, fillColor: werk ? "#5a6575" : ROT, fillOpacity: 0.95 });
        const box = document.createElement("div");
        const b = document.createElement("strong"); b.textContent = name;
        const a = document.createElement("a"); a.href = `#fw-${i}`; a.textContent = "Kontakt anzeigen";
        box.append(b, document.createElement("br"), document.createTextNode(ort), document.createElement("br"), a);
        m.bindPopup(box);
        marker[i] = m;
      });
    }

    function anwenden(zoomen) {
      const q = norm($("fw-q").value.trim()), g = $("fw-g").value;
      const sel = eintraege.filter((x) => (!q || x.suche.includes(q)) && (!g || x.g === g));
      const ids = new Set(sel.map((x) => x.i));
      eintraege.forEach((x) => { x.li.hidden = !ids.has(x.i); });
      // Gemeinden ohne Treffer ausblenden; ohne Filter alle zeigen (auch Gemeinden ohne Eintrag)
      gruppen.forEach((gr) => {
        gr.hidden = (q || g) ? !(gr.dataset.g === g && !q) && !gr.querySelector(".fw-eintrag:not([hidden])") : false;
        if (g && gr.dataset.g !== g) gr.hidden = true;
      });
      $("fw-treffer").textContent = `${nf.format(sel.length)} ${sel.length === 1 ? "Feuerwehrhaus" : "Feuerwehrhäuser"}`;
      const url = new URL(location.href);
      if (g) url.searchParams.set("g", g); else url.searchParams.delete("g");
      history.replaceState(null, "", url);
      if (layer) {
        layer.clearLayers();
        const ms = sel.map((x) => marker[x.i]).filter(Boolean);
        ms.forEach((m) => m.addTo(layer));
        if (zoomen && ms.length) map.fitBounds(L.latLngBounds(ms.map((m) => m.getLatLng())), { padding: [24, 24], maxZoom: 13 });
      }
    }

    $("fw-filter").addEventListener("input", () => anwenden(true));
    $("fw-filter").addEventListener("submit", (ev) => ev.preventDefault());
    anwenden(Boolean($("fw-g").value));
  });
})();
