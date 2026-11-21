/* Zeitschichten der Börde: Ereignisse aus /zeitschichten/ereignisse.geojson nach Zeitschichten auf einer Leaflet-Karte. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);

  // Zeitschichten von jung (oben) nach alt (unten). jahr < 0 heißt v. Chr. bzw. vor heute.
  const SCHICHTEN = [
    { id: "heute", n: "Gegenwart", r: "seit 1990", von: 1990, bis: 9999, farbe: "#EADDB0" },
    { id: "teilung", n: "Deutsche Teilung", r: "1945 – 1990", von: 1945.5, bis: 1990, farbe: "#D9C483" },
    { id: "krieg", n: "Weltkriege & NS-Zeit", r: "1914 – 1945", von: 1914, bis: 1945.5, farbe: "#C8A864" },
    { id: "industrie", n: "Zucker, Kohle, Eisenbahn", r: "1800 – 1914", von: 1800, bis: 1914, farbe: "#B58C4E" },
    { id: "neuzeit", n: "Frühe Neuzeit", r: "1500 – 1800", von: 1500, bis: 1800, farbe: "#9C713E", dunkel: true },
    { id: "mittelalter", n: "Hoch- & Spätmittelalter", r: "1100 – 1500", von: 1100, bis: 1500, farbe: "#835A35", dunkel: true },
    { id: "ottonen", n: "Frühmittelalter & Ottonen", r: "700 – 1100", von: 700, bis: 1100, farbe: "#6A4930", dunkel: true },
    { id: "metall", n: "Bronze-, Eisenzeit, Germanen", r: "2200 v. Chr. – 700", von: -2200, bis: 700, farbe: "#574034", dunkel: true },
    { id: "jung", n: "Jungsteinzeit", r: "5500 – 2200 v. Chr.", von: -5500, bis: -2200, farbe: "#40322A", dunkel: true },
    { id: "alt", n: "Altsteinzeit", r: "vor 400.000 – 10.000 J.", von: -1e7, bis: -5500, farbe: "#2A221D", dunkel: true },
  ];
  const GENAU = { objekt: "genau verortet", ortsmitte: "Lage: Ortsmitte", ungefaehr: "Lage nur ungefähr" };
  const RAND = "#3b2f25";

  let EV = [];
  const zustand = { schicht: null, sel: null, timer: null };
  let map = null;
  const marker = [];

  const schichtVon = (jahr) => SCHICHTEN.find((s) => jahr >= s.von && jahr < s.bis);

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function punkt(farbe) { const p = el("span", "zs-punkt"); p.style.background = farbe; return p; }

  // Karte -------------------------------------------------------------------
  function karte(gemeinden) {
    if (typeof L === "undefined") return;
    map = L.map("zs-karte", { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>, Grenzen &copy; GeoBasis-DE / BKG',
    }).addTo(map);
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    map.on("click focus", () => map.scrollWheelZoom.enable());
    let bounds = L.latLngBounds([[51.93, 10.9], [52.46, 11.8]]);
    if (gemeinden) {
      const g = L.geoJSON(gemeinden, {
        style: { color: "#6b5a3e", weight: 1.2, dashArray: "4 4", fill: true, fillColor: "#e9dcae", fillOpacity: 0.18 },
        interactive: false,
      }).addTo(map);
      bounds = g.getBounds();
    }
    // Erst setzen, dann nach dem Layout neu einpassen: beim ersten Aufruf hat der Kartencontainer evtl. noch keine Größe
    map.setView(bounds.getCenter(), 10);
    const einpassen = () => { map.invalidateSize(); map.fitBounds(bounds, { padding: [10, 10] }); };
    if (document.readyState === "complete") requestAnimationFrame(einpassen);
    else window.addEventListener("load", einpassen, { once: true });
    EV.forEach((e) => {
      const m = L.circleMarker([e.lat, e.lon], { radius: 8, color: RAND, weight: 1.6, fillColor: e.S.farbe, fillOpacity: 0.95 });
      m.bindTooltip(`${e.datum} · ${e.titel}`);
      m.on("click", () => { stopp(); waehle(e.i, true); });
      m.addTo(map);
      marker[e.i] = m;
    });
    map.on("zoomend", anordnen);
  }

  // Ereignisse am selben Ort ringförmig auffächern (in Bildschirmpixeln, daher bei jedem Zoom neu)
  function anordnen() {
    if (!map) return;
    const aktiv = EV.filter((e) => !zustand.schicht || e.S.id === zustand.schicht);
    const gruppen = {};
    aktiv.forEach((e) => { const k = `${e.lat.toFixed(3)},${e.lon.toFixed(3)}`; (gruppen[k] = gruppen[k] || []).push(e); });
    const pos = {};
    Object.values(gruppen).forEach((gr) => gr.forEach((e, j) => {
      if (gr.length === 1) { pos[e.i] = [e.lat, e.lon]; return; }
      const p = map.latLngToLayerPoint([e.lat, e.lon]);
      const w = -Math.PI / 2 + (j * 2 * Math.PI) / gr.length, r = 8 + 4 * gr.length;
      const ll = map.layerPointToLatLng(L.point(p.x + r * Math.cos(w), p.y + r * Math.sin(w)));
      pos[e.i] = [ll.lat, ll.lng];
    }));
    EV.forEach((e) => {
      const m = marker[e.i], an = !!pos[e.i], sel = zustand.sel === e.i;
      m.setLatLng(an ? pos[e.i] : [e.lat, e.lon]);
      m.setRadius(an ? (zustand.schicht ? 10 : 8) : 4);
      m.setStyle({ fillOpacity: an ? 0.95 : 0.3, opacity: an ? 1 : 0.35, weight: sel ? 3.5 : an ? 1.6 : 1 });
      if (an) m.bringToFront();
    });
    if (zustand.sel != null) marker[zustand.sel].bringToFront();
  }

  // Bodenprofil -------------------------------------------------------------
  const knoepfe = [];
  function profil() {
    const box = $("zs-schichten");
    SCHICHTEN.forEach((s) => {
      const b = el("button", "zs-schicht" + (s.dunkel ? " dunkel" : ""));
      b.type = "button";
      b.style.background = s.farbe;
      b.setAttribute("aria-pressed", "false");
      b.append(el("span", "n", s.n), el("span", "r", s.r), el("span", "c", String(EV.filter((e) => e.S === s).length)));
      b.addEventListener("click", () => { stopp(); setzeSchicht(zustand.schicht === s.id ? null : s.id); });
      box.append(b);
      knoepfe.push(b);
    });
  }

  function setzeSchicht(id) {
    zustand.schicht = id;
    SCHICHTEN.forEach((s, i) => knoepfe[i].setAttribute("aria-pressed", String(s.id === id)));
    $("zs-alle").setAttribute("aria-pressed", String(!id));
    const liste = EV.filter((e) => !id || e.S.id === id);
    if (zustand.sel != null && !liste.includes(EV[zustand.sel])) zustand.sel = null;
    if (zustand.sel == null && liste.length) zustand.sel = liste[0].i;
    zeigeListe(liste);
    anordnen();
    zeigeDetail();
  }

  function zeigeListe(liste) {
    const s = SCHICHTEN.find((x) => x.id === zustand.schicht);
    $("zs-listtitel").textContent = s ? s.n : "Alle Ereignisse";
    $("zs-anzahl").textContent = liste.length === 1 ? "1 Eintrag" : `${liste.length} Einträge`;
    const ul = $("zs-liste");
    ul.replaceChildren();
    if (!liste.length) {
      ul.append(el("li", "zs-leer", "Für diese Zeitschicht gibt es noch keine Einträge. Hier kann die Karte ergänzt werden."));
      return;
    }
    liste.slice().sort((a, b) => a.jahr - b.jahr).forEach((e) => {
      const li = el("li");
      const b = el("button", "zs-ev");
      b.type = "button";
      b.dataset.i = e.i;
      b.append(punkt(e.S.farbe), el("span", "y", e.datum), el("span", null, e.titel));
      b.addEventListener("click", () => { stopp(); waehle(e.i, false); });
      li.append(b);
      ul.append(li);
    });
    markiereListe();
  }
  function markiereListe() {
    document.querySelectorAll(".zs-ev").forEach((b) => b.setAttribute("aria-current", String(+b.dataset.i === zustand.sel)));
  }

  function zeigeDetail() {
    const box = $("zs-detail");
    box.replaceChildren();
    const e = EV[zustand.sel];
    if (!e) {
      const s = SCHICHTEN.find((x) => x.id === zustand.schicht);
      const kopf = el("div", "zs-datum"); kopf.append(punkt(s ? s.farbe : "transparent"), el("span", null, s ? s.r : ""));
      box.append(kopf, el("h3", null, "Noch keine Einträge"), el("p", null, "Diese Zeitschicht wartet auf Daten. Ergänzungen sind willkommen."));
      return;
    }
    const kopf = el("div", "zs-datum");
    kopf.append(punkt(e.S.farbe), el("span", null, `${e.datum} · ${e.S.n}`));
    const ort = el("p", "klein", `Ort: ${e.ort}${e.ausserhalb ? " (außerhalb des Landkreises)" : ""} · ${GENAU[e.genau] || ""}`);
    const a = el("a", null, `Quelle: Wikipedia – ${e.quelleTitel} ↗`);
    a.href = e.quelle; a.rel = "noopener";
    box.append(kopf, el("h3", null, e.titel), el("p", null, e.text), ort, a);
  }

  function waehle(i, vonKarte) {
    const e = EV[i];
    zustand.sel = i;
    if (zustand.schicht && e.S.id !== zustand.schicht) { setzeSchicht(e.S.id); return; }
    anordnen(); zeigeDetail(); markiereListe();
    if (vonKarte) { const b = document.querySelector(`.zs-ev[data-i="${i}"]`); if (b) b.scrollIntoView({ block: "nearest" }); }
    else if (map) map.panTo(marker[i].getLatLng());
  }

  // Zeitreise: von der Altsteinzeit bis heute ---------------------------------
  function stopp() {
    if (!zustand.timer) return;
    clearInterval(zustand.timer); zustand.timer = null;
    $("zs-play").textContent = "▶ Zeitreise starten";
  }
  function zeitreise() {
    if (zustand.timer) { stopp(); return; }
    const folge = SCHICHTEN.slice().reverse();
    let k = zustand.schicht ? folge.findIndex((s) => s.id === zustand.schicht) : 0;
    zustand.sel = null; setzeSchicht(folge[k].id);
    $("zs-play").textContent = "■ Anhalten";
    zustand.timer = setInterval(() => {
      k++;
      if (k >= folge.length) { stopp(); return; }
      zustand.sel = null; setzeSchicht(folge[k].id);
    }, 3200);
  }

  // Start -------------------------------------------------------------------
  const laden = (url) => fetch(url).then((r) => { if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); });

  document.addEventListener("DOMContentLoaded", () => {
    Promise.all([laden("/zeitschichten/ereignisse.geojson"), laden("/zeitschichten/gemeinden.geojson").catch(() => null)])
      .then(([fc, gemeinden]) => {
        EV = fc.features.map((f, i) => {
          const p = f.properties, [lon, lat] = f.geometry.coordinates;
          return { i, lat, lon, jahr: p.jahr, datum: p.datum, titel: p.titel, ort: p.ort, text: p.beschreibung,
            genau: p.lagegenauigkeit, ausserhalb: p.ausserhalb_landkreis, quelle: p.quelle_url, quelleTitel: p.quelle_titel,
            S: schichtVon(p.jahr) };
        }).filter((e) => e.S);
        EV.forEach((e, i) => { e.i = i; });
        profil();
        karte(gemeinden);
        $("zs-play").addEventListener("click", zeitreise);
        $("zs-alle").addEventListener("click", () => { stopp(); setzeSchicht(null); });
        setzeSchicht(null);
      })
      .catch(() => {
        const box = $("zs-detail");
        box.replaceChildren(el("h3", null, "Daten nicht geladen"),
          el("p", null, "Die Ereignisse konnten nicht geladen werden. Bitte laden Sie die Seite neu. Lokal funktioniert die Seite nur über einen Webserver, zum Beispiel mit python -m http.server."));
      });
  });
})();
