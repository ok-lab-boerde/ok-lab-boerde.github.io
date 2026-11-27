// Wahlatlas Börde: Karte mit Zeitreise, Kreisbalken und Verlaufsgrafiken
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const STRICH = { "Die Linke": "die-linke", "Grüne": "gruene", "Freie Wähler": "freie-waehler" };
  const klasse = (p) => (STRICH[p] || p.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
  const FAMILIEN = ["CDU", "AfD", "Die Linke", "SPD", "Grüne", "FDP", "DVU", "Freie Wähler", "BSW", "NPD", "REP", "Schill"];
  const farbe = (p) => `var(--p-${FAMILIEN.includes(p) ? klasse(p) : "sonstige"})`;
  const de = (x, n = 1) => x.toLocaleString("de-DE", { minimumFractionDigits: n, maximumFractionDigits: n });
  const MON = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
  const datum = (iso) => { const [j, m, t] = iso.split("-"); return `${+t}. ${MON[+m - 1]} ${j}`; };
  function anzeige(p, jahr) {
    if (p === "Die Linke") return jahr < 2005 ? "PDS" : jahr < 2007 ? "Linkspartei.PDS" : "Die Linke";
    if (p === "Grüne" && jahr === 1990) return "Bündnis 90/Grüne";
    if (p === "Schill") return "Schill-Partei";
    return p;
  }

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function tooltip(box) {
    const t = document.createElement("div");
    t.className = "wa-tip"; t.hidden = true; box.appendChild(t);
    return {
      show(html, x, y) {
        t.innerHTML = html; t.hidden = false;
        const bw = box.clientWidth, tw = t.offsetWidth;
        t.style.left = Math.max(0, Math.min(bw - tw, x + 14)) + "px";
        t.style.top = Math.max(0, y - t.offsetHeight - 12) + "px";
      },
      hide() { t.hidden = true; },
    };
  }
  const sortiert = (a) => Object.entries(a).filter(([p, v]) => v > 0 || p === "Sonstige")
    .sort((x, y) => (x[0] === "Sonstige") - (y[0] === "Sonstige") || y[1] - x[1]);
  const staerkste = (a) => sortiert(a).filter(([p]) => p !== "Sonstige")[0];

  // ------------------------------------------------------------ Verlaufsgrafik (Kreis oder Gemeinde)
  function verlauf(box, daten, werte) {
    box.textContent = "";
    const wahlen = daten.wahlen;
    const zeit = (w) => new Date(w.datum + "T00:00:00Z").getTime();
    const W = Math.max(320, box.clientWidth || 720), H = Math.round(Math.min(340, Math.max(240, W * 0.45)));
    const m = { l: 34, r: W < 500 ? 70 : 96, t: 12, b: 26 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const t0 = zeit(wahlen[0]), t1 = zeit(wahlen[wahlen.length - 1]);
    const X = (w) => m.l + ((zeit(w) - t0) / (t1 - t0)) * iw;
    // Familien, die irgendwann mindestens 5 % hatten
    const fam = FAMILIEN.filter((p) => wahlen.some((w) => (werte[w.id].anteile[p] || 0) >= 5));
    const ymax = Math.max(20, Math.ceil(Math.max(...wahlen.flatMap((w) => fam.map((p) => werte[w.id].anteile[p] || 0))) / 10) * 10);
    const Y = (v) => m.t + ih - (v / ymax) * ih;

    const leg = document.createElement("div");
    leg.className = "wa-legende";
    leg.innerHTML = fam.map((p) => `<span><i style="background:${farbe(p)}"></i>${p === "Die Linke" ? "PDS / Die Linke" : p}</span>`).join("");
    box.appendChild(leg);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Stimmenanteile der Parteien bei allen Wahlen seit 1990" }, box);
    for (let v = 0; v <= ymax; v += 10) {
      el("line", { x1: m.l, x2: m.l + iw, y1: Y(v), y2: Y(v), stroke: v ? "var(--wa-grid)" : "var(--wa-axis)", "stroke-width": 1 }, svg);
      el("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = v + (v === ymax ? " %" : "");
    }
    const schritt = W < 500 ? 10 : 5;
    for (let j = 1990; j <= +wahlen[wahlen.length - 1].datum.slice(0, 4); j += schritt) {
      const x = m.l + ((Date.UTC(j, 0, 1) - t0) / (t1 - t0)) * iw;
      if (x < m.l - 1) continue;
      el("line", { x1: x, x2: x, y1: m.t + ih, y2: m.t + ih + 4, stroke: "var(--wa-axis)" }, svg);
      el("text", { x, y: H - 8, "text-anchor": "middle" }, svg).textContent = j;
    }
    const enden = [];
    fam.forEach((p) => {
      let d = "", an = false, letzter = null;
      wahlen.forEach((w) => {
        const v = werte[w.id].anteile[p];
        if (v == null) { an = false; return; }
        d += `${an ? "L" : "M"}${X(w).toFixed(1)},${Y(v).toFixed(1)}`; an = true; letzter = w;
      });
      el("path", { d, fill: "none", style: `stroke:${farbe(p)}`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
      wahlen.forEach((w) => {
        const v = werte[w.id].anteile[p];
        if (v == null) return;
        el("circle", { cx: X(w), cy: Y(v), r: 2.6, style: `fill:${farbe(p)}` }, svg);
      });
      const wl = wahlen[wahlen.length - 1];
      if (letzter === wl) enden.push({ p, y: Y(werte[wl.id].anteile[p]) });
    });
    enden.sort((a, b) => a.y - b.y);
    for (let i = 1; i < enden.length; i++) if (enden[i].y - enden[i - 1].y < 13) enden[i].y = enden[i - 1].y + 13;
    enden.forEach((e) => { el("text", { x: m.l + iw + 8, y: e.y + 4, class: "lbl" }, svg).textContent = e.p; });

    const kreuz = el("line", { y1: m.t, y2: m.t + ih, stroke: "var(--wa-axis)", visibility: "hidden" }, svg);
    const hit = el("rect", { x: m.l - 6, y: m.t, width: iw + 12, height: ih, fill: "transparent" }, svg);
    const tip = tooltip(box);
    function zeigen(ev) {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      const w = wahlen.reduce((a, b) => (Math.abs(X(b) - px) < Math.abs(X(a) - px) ? b : a));
      kreuz.setAttribute("x1", X(w)); kreuz.setAttribute("x2", X(w)); kreuz.setAttribute("visibility", "visible");
      const x = werte[w.id];
      const zeilen = sortiert(x.anteile).filter(([p, v]) => v >= 1 || p === "Sonstige").slice(0, 7)
        .map(([p, v]) => `<i style="background:${farbe(p)}"></i>${anzeige(p, w.jahr)}: ${de(v)} %`).join("<br>");
      tip.show(`<b>${w.titel}</b>${zeilen}<br><small>Wahlbeteiligung ${de(x.beteiligung)} %${x.briefwahl ? "" : ", ohne Briefwahl"}</small>`,
        (X(w) / W) * r.width, (m.t / H) * r.height + 10);
    }
    hit.addEventListener("pointermove", zeigen);
    hit.addEventListener("pointerdown", zeigen);
    hit.addEventListener("pointerleave", () => { tip.hide(); kreuz.setAttribute("visibility", "hidden"); });
  }

  // ------------------------------------------------------------ Karte
  function karte(box, geo, daten) {
    box.textContent = "";
    const nachName = {};
    Object.values(daten.gemeinden).forEach((g) => { nachName[g.name] = g; });
    let lon0 = Infinity, lon1 = -Infinity, lat0 = Infinity, lat1 = -Infinity;
    const ringe = (geom) => (geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates);
    geo.features.forEach((f) => ringe(f.geometry).forEach((poly) => poly.forEach((ring) => ring.forEach(([x, y]) => {
      lon0 = Math.min(lon0, x); lon1 = Math.max(lon1, x); lat0 = Math.min(lat0, y); lat1 = Math.max(lat1, y);
    }))));
    const k = Math.cos(((lat0 + lat1) / 2) * Math.PI / 180);
    const W = 600, H = Math.round(W * ((lat1 - lat0) / ((lon1 - lon0) * k)));
    const P = ([x, y]) => [((x - lon0) * k) / ((lon1 - lon0) * k) * W, ((lat1 - y) / (lat1 - lat0)) * H];
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Karte der 34 Gemeinden im Landkreis Börde" }, box);
    const flaechen = geo.features.map((f) => {
      const d = ringe(f.geometry).map((poly) => poly.map((ring) => ring.map((c, i) => (i ? "L" : "M") + P(c).map((v) => v.toFixed(1)).join(",")).join("") + "Z").join("")).join("");
      const g = nachName[f.properties.name];
      const p = el("path", { d, tabindex: "0", role: "link", "aria-label": g ? g.name : f.properties.name }, svg);
      return { p, g };
    });
    const tip = tooltip(box);
    return { flaechen, tip, svg };
  }

  function stufen(v, grenzen) { let i = 0; while (i < grenzen.length && v >= grenzen[i]) i++; return i; }

  function faerben(k, daten, w, ansicht, legende) {
    const BET = [40, 50, 60, 70, 80];
    const ANT = [10, 20, 30, 40, 50];
    k.flaechen.forEach(({ p, g }) => {
      if (!g) { p.style.fill = "var(--wa-leer)"; return; }
      const x = g.wahlen[w.id];
      if (ansicht === "staerkste") {
        p.style.fill = farbe(staerkste(x.anteile)[0]);
        p.style.fillOpacity = 1;
      } else if (ansicht === "beteiligung") {
        p.style.fill = "rgb(var(--wa-beteiligung))";
        p.style.fillOpacity = (0.15 + stufen(x.beteiligung, BET) * 0.17).toFixed(2);
      } else {
        const v = x.anteile[ansicht];
        if (v == null || (v === 0 && !daten.spalten[w.id].includes(ansicht))) { p.style.fill = "var(--wa-leer)"; p.style.fillOpacity = 1; return; }
        p.style.fill = farbe(ansicht);
        p.style.fillOpacity = (0.12 + stufen(v, ANT) * 0.176).toFixed(2);
      }
    });
    let html = "";
    if (ansicht === "staerkste") {
      const vorne = [...new Set(k.flaechen.filter((f) => f.g).map((f) => staerkste(f.g.wahlen[w.id].anteile)[0]))];
      html = vorne.map((p) => `<span><i style="background:${farbe(p)}"></i>${anzeige(p, w.jahr)} vorn</span>`).join("");
    } else if (ansicht === "beteiligung") {
      html = ["unter 40", "40–50", "50–60", "60–70", "70–80", "über 80"].map((t, i) =>
        `<span><i style="background:rgb(var(--wa-beteiligung));opacity:${(0.15 + i * 0.17).toFixed(2)}"></i>${t} %</span>`).join("");
    } else if (!daten.spalten[w.id].includes(ansicht)) {
      html = `<span>${anzeige(ansicht, w.jahr)} ist bei dieser Wahl nicht angetreten oder blieb im Kreis unter 3 % (unter „Sonstige“).</span>`;
    } else {
      html = ["unter 10", "10–20", "20–30", "30–40", "40–50", "über 50"].map((t, i) =>
        `<span><i style="background:${farbe(ansicht)};opacity:${(0.12 + i * 0.176).toFixed(2)}"></i>${t} %</span>`).join("");
    }
    legende.innerHTML = html;
  }

  function balkenHtml(a, jahr) {
    return '<div class="wa-balken-liste">' + sortiert(a).map(([p, v]) =>
      `<div class="wa-zeile"><span class="wa-partei">${anzeige(p, jahr)}</span><span class="wa-spur"><span class="wa-balken" style="width:${Math.min(v, 100)}%;background:${farbe(p)}"></span></span><span class="wa-wert">${de(v)} %</span></div>`).join("") + "</div>";
  }

  async function atlas() {
    const box = document.getElementById("wa-map");
    if (!box) return;
    let daten, geo;
    try {
      [daten, geo] = await Promise.all([fetch("/wahlen/data.json").then((r) => r.json()), fetch("/zeitschichten/gemeinden.geojson").then((r) => r.json())]);
    } catch (err) {
      box.textContent = "Die Karte konnte nicht geladen werden. Die Ergebnisse stehen in den Tabellen unten.";
      return;
    }
    const wahlen = daten.wahlen;
    const k = karte(box, geo, daten);
    const regler = document.getElementById("wa-zeit");
    const ausgabe = document.getElementById("wa-zeit-text");
    const ansichtSel = document.getElementById("wa-ansicht");
    const legende = document.getElementById("wa-legende");
    const hinweis = document.getElementById("wa-hinweis");
    const kreisBalken = document.getElementById("wa-kreis-balken");
    const kreisText = document.getElementById("wa-kreis-text");
    const play = document.getElementById("wa-play");
    let liste = wahlen.slice(), aktuell = wahlen[wahlen.length - 1], timer = null;

    function zeigen(w) {
      aktuell = w;
      const ansicht = ansichtSel.value;
      ausgabe.textContent = `${w.titel} · ${datum(w.datum)}`;
      faerben(k, daten, w, ansicht, legende);
      const kr = daten.kreis[w.id];
      kreisBalken.innerHTML = balkenHtml(kr.anteile, w.jahr);
      kreisText.textContent = `${w.stimme} im Landkreis Börde, Wahlbeteiligung ${de(kr.beteiligung)} %${kr.briefwahl ? "" : " (ohne Briefwahl)"}.`;
      hinweis.hidden = w.briefwahl;
      hinweis.textContent = w.briefwahl ? "" : `Bei der ${w.titel} wurde die Briefwahl nicht nach Gemeinden ausgezählt. Die Gemeindewerte enthalten nur die Stimmen aus den Wahllokalen${w.jahr < 2007 ? "; den Landkreis Börde gab es noch nicht, die Werte sind auf die heutigen Gemeinden umgerechnet" : ""}.`;
    }
    function setzeListe(art) {
      liste = art === "alle" ? wahlen.slice() : wahlen.filter((w) => w.art === art);
      regler.max = liste.length - 1;
      const i = liste.indexOf(aktuell);
      regler.value = i >= 0 ? i : liste.length - 1;
      zeigen(liste[+regler.value]);
    }
    regler.addEventListener("input", () => { stoppen(); zeigen(liste[+regler.value]); });
    ansichtSel.addEventListener("change", () => zeigen(aktuell));
    document.querySelectorAll(".wa-filter [data-art]").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(".wa-filter [data-art]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      stoppen(); setzeListe(b.dataset.art);
    }));
    function stoppen() { if (timer) { clearInterval(timer); timer = null; play.textContent = "▶"; play.setAttribute("aria-label", "Alle Wahlen nacheinander abspielen"); } }
    play.addEventListener("click", () => {
      if (timer) { stoppen(); return; }
      if (+regler.value >= liste.length - 1) regler.value = 0;
      zeigen(liste[+regler.value]);
      play.textContent = "❚❚"; play.setAttribute("aria-label", "Abspielen anhalten");
      timer = setInterval(() => {
        if (+regler.value >= liste.length - 1) { stoppen(); return; }
        regler.value = +regler.value + 1; zeigen(liste[+regler.value]);
      }, 1400);
    });

    k.flaechen.forEach(({ p, g }) => {
      if (!g) return;
      const zeig = (ev) => {
        const x = g.wahlen[aktuell.id];
        const r = box.getBoundingClientRect();
        const zeilen = sortiert(x.anteile).slice(0, 4).map(([pp, v]) => `<i style="background:${farbe(pp)}"></i>${anzeige(pp, aktuell.jahr)}: ${de(v)} %`).join("<br>");
        const cx = ev.clientX != null ? ev.clientX - r.left : r.width / 2, cy = ev.clientY != null ? ev.clientY - r.top : 40;
        k.tip.show(`<b>${g.name}</b><small>${aktuell.titel}</small><br>${zeilen}<br><small>Wahlbeteiligung ${de(x.beteiligung)} %${aktuell.briefwahl ? "" : " (ohne Briefwahl)"}</small>`, cx, cy);
      };
      p.addEventListener("pointermove", zeig);
      p.addEventListener("focus", (ev) => zeig({}));
      p.addEventListener("pointerleave", k.tip.hide);
      p.addEventListener("blur", k.tip.hide);
      p.addEventListener("click", () => { location.href = `/wahlen/${g.slug}/`; });
      p.addEventListener("keydown", (ev) => { if (ev.key === "Enter") location.href = `/wahlen/${g.slug}/`; });
    });
    zeigen(aktuell);

    const trend = document.getElementById("wa-trend-chart");
    if (trend) {
      const werte = {};
      wahlen.forEach((w) => { werte[w.id] = daten.kreis[w.id]; });
      const malen = () => verlauf(trend, daten, werte);
      malen();
      let breite = trend.clientWidth, t;
      window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => { if (trend.clientWidth !== breite) { breite = trend.clientWidth; malen(); } }, 150); });
    }
  }

  async function gemeinde() {
    const box = document.getElementById("wa-gem-chart");
    if (!box) return;
    let daten;
    try { daten = await fetch("/wahlen/data.json").then((r) => r.json()); } catch (err) { box.remove(); return; }
    const g = daten.gemeinden[box.dataset.ags];
    if (!g) return;
    const werte = {};
    daten.wahlen.forEach((w) => { werte[w.id] = { ...g.wahlen[w.id], briefwahl: w.briefwahl }; });
    const malen = () => verlauf(box, daten, werte);
    malen();
    let breite = box.clientWidth, t;
    window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => { if (box.clientWidth !== breite) { breite = box.clientWidth; malen(); } }, 150); });
  }

  const start = () => { atlas(); gemeinde(); };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
