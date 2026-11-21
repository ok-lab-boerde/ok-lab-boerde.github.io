/* Ratskarte: Punkte (Straßen, Orte) und Tagesordnungspunkte aus #rk-daten, Filter und Liste. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("de-DE");
  const FARBE = { strasse: "#0d4a8f", ort: "#2e7d32" };
  const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
  const datum = (d) => `${d.slice(8, 10)}.${d.slice(5, 7)}.${d.slice(0, 4)}`;

  document.addEventListener("DOMContentLoaded", () => {
    const D = JSON.parse($("rk-daten").textContent);
    const punkte = D.punkte.map(([k, name, lat, lon, art, e]) => ({ k, name, lat, lon, art, e }));
    const P = Object.fromEntries(punkte.map((p) => [p.k, p]));
    const E = D.eintraege.map(([d, gr, si, to, t, b, vo, vn, z], i) => ({
      i, d, gr, si, to, t, b, vo, vn, z, suche: norm(`${t} ${gr} ${vn} ${z.map((k) => P[k].name).join(" ")}`),
    }));

    let map = null;
    const marker = {};
    if (typeof L !== "undefined") {
      map = L.map("rk-karte", { scrollWheelZoom: false, preferCanvas: true });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
      }).addTo(map);
      map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
      map.on("click focus", () => map.scrollWheelZoom.enable());
      map.setView([52.06, 11.44], 11);
      punkte.forEach((p) => {
        const r = p.art === "ort" ? 9 : 6;
        const m = L.circleMarker([p.lat, p.lon], { radius: r, color: "#fff", weight: 1.5, fillColor: FARBE[p.art], fillOpacity: 0.9 });
        m.bindTooltip(`${p.name}: ${nf.format(p.e.length)}`);
        m.on("click", () => { $("rk-ort").value = p.k; anwenden(false); $("rk-treffer").scrollIntoView({ behavior: "smooth", block: "start" }); });
        marker[p.k] = m;
      });
    }

    function link(href, text) {
      const a = document.createElement("a"); a.href = href; a.textContent = text; a.rel = "noopener"; return a;
    }

    function zeile(x) {
      const li = document.createElement("li");
      const kopf = document.createElement("p"); kopf.className = "klein";
      kopf.textContent = `${datum(x.d)} · ${x.gr}`;
      const titel = document.createElement("p"); titel.className = "rk-titel";
      titel.append(link(`${D.basis}to0050.asp?__ktonr=${x.to}`, x.t));
      const info = document.createElement("p"); info.className = "klein";
      x.z.forEach((k, n) => {
        if (n) info.append(", ");
        const b = document.createElement("button"); b.type = "button"; b.className = "rk-ziel"; b.textContent = P[k].name;
        b.addEventListener("click", () => { $("rk-ort").value = k; anwenden(true); });
        info.append(b);
      });
      if (x.b) info.append(` · Beschluss: ${x.b}`);
      if (x.vo) { info.append(" · Vorlage "); info.append(link(`${D.basis}vo0050.asp?__kvonr=${x.vo}`, x.vn)); }
      info.append(" · "); info.append(link(`${D.basis}si0057.asp?__ksinr=${x.si}`, "Sitzung"));
      li.append(kopf, titel, info);
      return li;
    }

    function anwenden(zoomen) {
      const q = norm($("rk-q").value.trim()), ort = $("rk-ort").value, gr = $("rk-gr").value, jahr = $("rk-jahr").value;
      const sel = E.filter((x) => (!q || x.suche.includes(q)) && (!ort || x.z.includes(ort)) && (!gr || x.gr === gr) &&
        (!jahr || x.d.startsWith(jahr)));
      const liste = $("rk-liste");
      liste.replaceChildren(...sel.slice(0, 200).map(zeile));
      $("rk-treffer").textContent = `${nf.format(sel.length)} Tagesordnungspunkte` +
        (sel.length > 200 ? " · die neuesten 200 werden angezeigt, Filter grenzen weiter ein" : "");
      if (map) {
        const aktiv = new Set(sel.flatMap((x) => x.z));
        punkte.forEach((p) => {
          const m = marker[p.k];
          if (aktiv.has(p.k)) {
            const stil = { weight: p.k === ort ? 3 : 1.5, color: p.k === ort ? "#000" : "#fff" };
            if (map.hasLayer(m)) m.setStyle(stil); else { L.Util.setOptions(m, stil); m.addTo(map); }
          }
          else if (map.hasLayer(m)) map.removeLayer(m);
        });
        const pts = [...aktiv].map((k) => [P[k].lat, P[k].lon]);
        if (ort && P[ort] && zoomen) map.setView([P[ort].lat, P[ort].lon], P[ort].art === "ort" ? 14 : 16);
        else if (pts.length && (zoomen || !map._loaded)) map.fitBounds(L.latLngBounds(pts), { padding: [24, 24], maxZoom: 15 });
        else if (!map._loaded) map.setView([52.06, 11.44], 11);
      }
    }

    $("rk-filter").addEventListener("input", () => anwenden(true));
    $("rk-filter").addEventListener("submit", (ev) => ev.preventDefault());
    anwenden(true);
  });
})();
