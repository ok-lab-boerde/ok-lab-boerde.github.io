/* Kleine Karten auf Betriebs- und Ortsseiten + "jetzt geöffnet"-Anzeige. Benötigt Leaflet (lokal). */
(() => {
  "use strict";
  const FARBE = "#0d4a8f";

  function karte(div, d) {
    const map = L.map(div, { scrollWheelZoom: false, preferCanvas: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
    }).addTo(map);
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    map.on("click focus", () => map.scrollWheelZoom.enable());
    let bounds = null;
    if (d.grenze) {
      const g = L.geoJSON({ type: "MultiPolygon", coordinates: d.grenze }, { style: { color: FARBE, weight: 2.5, fill: true, fillOpacity: 0.04, dashArray: "6 4" }, interactive: false }).addTo(map);
      bounds = g.getBounds();
    }
    const layer = d.cluster && L.markerClusterGroup ? L.markerClusterGroup({
      showCoverageOnHover: false, maxClusterRadius: 40,
      iconCreateFunction: (c) => { const n = c.getChildCount(), s = n < 10 ? 28 : n < 100 ? 34 : 40;
        return L.divIcon({ html: `<div class="cluster" style="width:${s}px;height:${s}px">${n}</div>`, className: "", iconSize: [s, s] }); },
    }) : L.layerGroup();
    (d.punkte || []).forEach(([lat, lon, name, url]) => {
      const m = L.circleMarker([lat, lon], { radius: 6, color: "#fff", weight: 1.5, fillColor: FARBE, fillOpacity: 0.95 });
      const a = document.createElement(url ? "a" : "strong");
      a.textContent = name;
      if (url) a.href = url;
      m.bindPopup(a);
      layer.addLayer(m);
    });
    layer.addTo(map);
    if (d.zentrum) map.setView(d.zentrum, d.zoom || 15);
    else if (bounds) map.fitBounds(bounds, { padding: [8, 8] });
    else if ((d.punkte || []).length) map.fitBounds(L.latLngBounds(d.punkte.map((p) => [p[0], p[1]])), { padding: [20, 20] });
  }

  document.querySelectorAll(".ok-karte").forEach((div) => {
    const s = div.nextElementSibling;
    if (!s || !s.classList.contains("ok-karte-daten") || typeof L === "undefined") return;
    try { karte(div, JSON.parse(s.textContent)); } catch (err) { div.remove(); }
  });

  // "Jetzt geöffnet" anhand der vorberechneten Wochentabelle (Mo=0 .. So=6), Ortszeit des Browsers
  window.okOffen = function (woche, jetzt = new Date()) {
    const tag = (jetzt.getDay() + 6) % 7, min = jetzt.getHours() * 60 + jetzt.getMinutes();
    return (woche[tag] || []).some(([a, b]) => min >= a && min < b);
  };
  document.querySelectorAll(".jetzt[data-woche]").forEach((p) => {
    const woche = JSON.parse(p.dataset.woche);
    const auf = window.okOffen(woche);
    p.innerHTML = auf ? '<span class="auf">● Jetzt geöffnet</span>' : '<span class="zu">○ Jetzt geschlossen</span>';
    p.insertAdjacentHTML("beforeend", ' <span class="klein">(laut Öffnungszeiten, ohne Feiertage)</span>');
    const zeilen = p.parentElement.querySelectorAll(".oz tr");
    const heute = (new Date().getDay() + 6) % 7;
    if (zeilen[heute]) zeilen[heute].classList.add("heute");
  });
})();
