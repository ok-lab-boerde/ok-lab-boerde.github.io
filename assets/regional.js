/* Regional einkaufen: Karte und Liste filtern. Die Einträge stehen als HTML in #rg-liste, die Punkte in #rg-daten. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("de-DE");
  const FARBE = "#2e7d32";
  const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");

  document.addEventListener("DOMContentLoaded", () => {
    const karten = [...document.querySelectorAll("#rg-liste .reg-karte")].map((li) => ({
      li, id: li.dataset.i, art: li.dataset.art, g: li.dataset.g,
      p: li.dataset.p ? li.dataset.p.split(",") : [],
      woche: li.dataset.woche ? JSON.parse(li.dataset.woche) : null,
      saison: li.dataset.saison ? li.dataset.saison.split(",").map(Number) : null,
      suche: norm(li.textContent),
    }));
    const monat = new Date().getMonth() + 1;

    // Status je Karte: jetzt geöffnet / Saison
    karten.forEach((k) => {
      const s = k.li.querySelector(".jetzt-kurz");
      if (s && k.woche) s.innerHTML = window.okOffen(k.woche) ? '<strong class="auf">● geöffnet</strong> · ' : "";
      if (k.saison && !k.saison.includes(monat)) k.li.classList.add("ausser-saison");
    });

    let map = null, cluster = null;
    const marker = {};
    if (typeof L !== "undefined") {
      map = L.map("rg-karte", { scrollWheelZoom: false, preferCanvas: true });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
      }).addTo(map);
      map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
      map.on("click focus", () => map.scrollWheelZoom.enable());
      cluster = L.markerClusterGroup({
        showCoverageOnHover: false, maxClusterRadius: 35,
        iconCreateFunction: (c) => { const n = c.getChildCount(), s = n < 10 ? 28 : 34;
          return L.divIcon({ html: `<div class="cluster gruen" style="width:${s}px;height:${s}px">${n}</div>`, className: "", iconSize: [s, s] }); },
      }).addTo(map);
      JSON.parse($("rg-daten").textContent).forEach(([lat, lon, name, url, id]) => {
        const m = L.circleMarker([lat, lon], { radius: 7, color: "#fff", weight: 1.5, fillColor: FARBE, fillOpacity: 0.95 });
        const box = document.createElement("div");
        const a = document.createElement("a"); a.href = url; a.textContent = name;
        const z = document.createElement("a"); z.href = `#r-${id}`; z.textContent = "Kontakt anzeigen";
        box.append(a, document.createElement("br"), z);
        m.bindPopup(box);
        marker[id] = m;
      });
    }

    function anwenden(zoomen) {
      const q = norm($("rg-q").value.trim()), prod = $("rg-prod").value, g = $("rg-gem").value, offen = $("rg-offen").checked;
      const arten = [...document.querySelectorAll('#rg-filter input[name="art"]:checked')].map((x) => x.value);
      const jetzt = new Date();
      const sel = karten.filter((k) =>
        (!q || k.suche.includes(q)) && (prod === "" || k.p.includes(prod)) && (g === "" || k.g === g) &&
        (!arten.length || arten.includes(k.art)) && (!offen || (k.woche && window.okOffen(k.woche, jetzt))));
      const ids = new Set(sel.map((k) => k.id));
      karten.forEach((k) => { k.li.hidden = !ids.has(k.id); });
      $("rg-treffer").textContent = `${nf.format(sel.length)} ${sel.length === 1 ? "Eintrag" : "Einträge"}` +
        (prod !== "" ? " · Einträge ohne Angaben zum Angebot sind ausgeblendet, viele Hofläden haben noch keine." : "");
      if (cluster) {
        cluster.clearLayers();
        cluster.addLayers(sel.map((k) => marker[k.id]).filter(Boolean));
        const pts = sel.map((k) => marker[k.id]).filter(Boolean).map((m) => m.getLatLng());
        if (pts.length && (zoomen || !map._loaded)) map.fitBounds(L.latLngBounds(pts), { padding: [24, 24], maxZoom: 14 });
        else if (!map._loaded) map.setView([52.2, 11.3], 9);
      }
    }

    $("rg-filter").addEventListener("input", () => anwenden(true));
    $("rg-filter").addEventListener("submit", (ev) => ev.preventDefault());
    anwenden(true);
  });
})();
