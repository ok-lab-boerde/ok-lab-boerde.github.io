// Börde-Quiz: Gemeinden, Ortsteile und Orte auf der Karte finden. Läuft komplett im Browser, speichert nichts.
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const FRAGEN = 10;
  const de = (x, n = 1) => x.toLocaleString("de-DE", { minimumFractionDigits: n, maximumFractionDigits: n });

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function mischen(a) {
    const b = a.slice();
    for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [b[i], b[j]] = [b[j], b[i]]; }
    return b;
  }
  function km(lon1, lat1, lon2, lat2) {
    const r = Math.PI / 180, a = Math.sin(((lat2 - lat1) * r) / 2) ** 2 +
      Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(a));
  }

  async function start() {
    const box = document.getElementById("qz-karte");
    if (!box) return;
    let daten, geo;
    try {
      [daten, geo] = await Promise.all([fetch("/quiz/data.json").then((r) => r.json()),
        fetch("/zeitschichten/gemeinden.geojson").then((r) => r.json())]);
    } catch (err) {
      document.getElementById("qz-text").textContent = "Die Karte konnte nicht geladen werden.";
      return;
    }

    // Karte zeichnen
    const ringe = (g) => (g.type === "Polygon" ? [g.coordinates] : g.coordinates);
    let lon0 = Infinity, lon1 = -Infinity, lat0 = Infinity, lat1 = -Infinity;
    geo.features.forEach((f) => ringe(f.geometry).forEach((p) => p.forEach((r) => r.forEach(([x, y]) => {
      lon0 = Math.min(lon0, x); lon1 = Math.max(lon1, x); lat0 = Math.min(lat0, y); lat1 = Math.max(lat1, y);
    }))));
    const k = Math.cos(((lat0 + lat1) / 2) * Math.PI / 180);
    const W = 600, H = Math.round(W * ((lat1 - lat0) / ((lon1 - lon0) * k)));
    const P = (x, y) => [((x - lon0) / (lon1 - lon0)) * W, ((lat1 - y) / (lat1 - lat0)) * H];
    const R = (px, py) => [lon0 + (px / W) * (lon1 - lon0), lat1 - (py / H) * (lat1 - lat0)];
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "application", "aria-label": "Karte des Landkreises Börde mit 34 Gemeinden" }, box);
    const flaechen = {};
    geo.features.forEach((f) => {
      const name = f.properties.name;
      let sx = 0, sy = 0, n = 0;
      const d = ringe(f.geometry).map((poly) => poly.map((ring) => ring.map(([x, y], i) => {
        if (poly === ringe(f.geometry)[0]) { sx += x; sy += y; n++; }
        const [a, b] = P(x, y); return (i ? "L" : "M") + a.toFixed(1) + "," + b.toFixed(1);
      }).join("") + "Z").join("")).join("");
      const p = el("path", { d, tabindex: "0", "aria-label": "Gemeinde" }, svg);
      p.dataset.name = name;
      flaechen[name] = { p, lon: sx / n, lat: sy / n };
    });
    const schicht = el("g", {}, svg);

    const frage = document.getElementById("qz-text");
    const runde = document.getElementById("qz-runde");
    const punkte = document.getElementById("qz-punkte");
    const rueck = document.getElementById("qz-rueck");
    const weiter = document.getElementById("qz-weiter");
    const modusKnoepfe = document.querySelectorAll(".qz-modi button");
    let modus = "gemeinde", fragen = [], nr = 0, stand = 0, offen = false;

    function aufraeumen() {
      Object.values(flaechen).forEach(({ p }) => p.classList.remove("qz-richtig", "qz-falsch", "qz-ziel"));
      schicht.textContent = "";
    }
    function beschriften(name) {
      const f = flaechen[name];
      const [x, y] = P(f.lon, f.lat);
      el("text", { x, y, "text-anchor": "middle" }, schicht).textContent = name;
    }
    function anzeigen() {
      runde.textContent = `Frage ${nr + 1} von ${FRAGEN}`;
      punkte.textContent = modus === "genau" ? `${stand} Punkte` : `${stand} richtig`;
    }

    function neueRunde() {
      aufraeumen();
      nr = 0; stand = 0;
      if (modus === "gemeinde") fragen = mischen(daten.gemeinden.map((g) => g.name)).slice(0, FRAGEN);
      else if (modus === "ortsteil") fragen = mischen(daten.ortsteile).slice(0, FRAGEN);
      else fragen = mischen(daten.orte).slice(0, FRAGEN);
      stellen();
    }
    function stellen() {
      aufraeumen();
      const f = fragen[nr];
      frage.innerHTML = modus === "gemeinde" ? `Wo liegt <b>${f}</b>?`
        : modus === "ortsteil" ? `Zu welcher Gemeinde gehört <b>${f[0]}</b>?`
          : `Tippe auf <b>${f[0]}</b>`;
      rueck.textContent = modus === "genau" ? "Je näher, desto mehr Punkte. Bis 10 km Abstand gibt es noch etwas." : "";
      weiter.hidden = true;
      box.classList.add("qz-aktiv");
      box.classList.toggle("qz-genau", modus === "genau");
      offen = true;
      anzeigen();
    }
    function beantwortet() {
      offen = false;
      box.classList.remove("qz-aktiv");
      weiter.hidden = false;
      weiter.textContent = nr + 1 < FRAGEN ? "Nächste Frage" : "Ergebnis zeigen";
      anzeigen();
      weiter.focus({ preventScroll: true });
    }

    function waehleGemeinde(name) {
      if (!offen || modus === "genau") return;
      const f = fragen[nr];
      const ziel = modus === "gemeinde" ? f : f[1];
      if (name === ziel) {
        stand++;
        flaechen[name].p.classList.add("qz-richtig");
        rueck.innerHTML = modus === "gemeinde" ? `<span class="ok">Richtig!</span> Das ist ${ziel}.`
          : `<span class="ok">Richtig!</span> ${f[0]} gehört zu ${ziel}.`;
      } else {
        flaechen[name].p.classList.add("qz-falsch");
        flaechen[ziel].p.classList.add("qz-ziel");
        const abstand = km(flaechen[name].lon, flaechen[name].lat, flaechen[ziel].lon, flaechen[ziel].lat);
        rueck.innerHTML = `<span class="nein">Leider nicht.</span> Das war ${name}. ` +
          (modus === "gemeinde" ? `${ziel} liegt rund ${de(abstand, 0)} km entfernt.` : `${f[0]} gehört zu ${ziel}.`);
        beschriften(name);
      }
      beschriften(ziel);
      beantwortet();
    }
    function tippeGenau(ev) {
      if (!offen || modus !== "genau") return;
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W, py = ((ev.clientY - r.top) / r.height) * H;
      const [lon, lat] = R(px, py);
      const [name, gem, zlon, zlat] = fragen[nr];
      const abstand = km(lon, lat, zlon, zlat);
      const p = Math.max(0, Math.round(100 - abstand * 10));
      stand += p;
      const [zx, zy] = P(zlon, zlat);
      el("line", { x1: px, y1: py, x2: zx, y2: zy, class: "qz-linie" }, schicht);
      el("circle", { cx: px, cy: py, r: 6, class: "qz-marke-klick" }, schicht);
      el("circle", { cx: zx, cy: zy, r: 7, class: "qz-marke-ziel" }, schicht);
      el("text", { x: zx, y: zy - 12, "text-anchor": "middle" }, schicht).textContent = name;
      rueck.innerHTML = (abstand < 1.5 ? '<span class="ok">Volltreffer!</span> ' : abstand < 5 ? '<span class="ok">Nah dran.</span> ' : '<span class="nein">Daneben.</span> ')
        + `${de(abstand)} km entfernt, ${p} Punkte. ${name} liegt in der Gemeinde ${gem}.`;
      beantwortet();
    }
    function ergebnis() {
      aufraeumen();
      box.classList.remove("qz-aktiv");
      const max = modus === "genau" ? FRAGEN * 100 : FRAGEN;
      const anteil = stand / max;
      const urteil = anteil >= 0.95 ? "Börde-Profi! Dir macht keiner was vor."
        : anteil >= 0.7 ? "Stark, du kennst dich richtig gut aus."
          : anteil >= 0.4 ? "Ordentlich. Da geht beim nächsten Mal noch mehr."
            : "Zeit für einen Ausflug durch die Börde!";
      runde.textContent = "Ergebnis";
      punkte.textContent = "";
      frage.innerHTML = modus === "genau" ? `<b>${stand}</b> von ${max} Punkten` : `<b>${stand}</b> von ${max} richtig`;
      rueck.textContent = urteil;
      weiter.hidden = false;
      weiter.textContent = "Neue Runde";
      fragen = [];
    }

    Object.values(flaechen).forEach(({ p }) => {
      p.addEventListener("click", () => { if (modus !== "genau") waehleGemeinde(p.dataset.name); });
      p.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); waehleGemeinde(p.dataset.name); } });
    });
    svg.addEventListener("click", (ev) => { if (modus === "genau") tippeGenau(ev); });
    weiter.addEventListener("click", () => {
      if (!fragen.length) { neueRunde(); return; }
      if (nr + 1 < FRAGEN) { nr++; stellen(); } else ergebnis();
    });
    modusKnoepfe.forEach((b) => b.addEventListener("click", () => {
      modusKnoepfe.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      modus = b.dataset.modus;
      neueRunde();
    }));
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
