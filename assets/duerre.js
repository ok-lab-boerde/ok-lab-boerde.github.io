// Dürremonitor Börde: Verlauf der Bodenfeuchte und Trockenstress-Tage je Jahr
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const MON = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  const fmt = (v) => (v == null ? "–" : String(Math.round(v)).replace(".", ","));
  const datumDe = (d) => `${d.getUTCDate()}. ${MON[d.getUTCMonth()]} ${d.getUTCFullYear()}`;

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  function tagIndex(d) {
    const y = d.getUTCFullYear();
    let i = Math.round((d - Date.UTC(y, 0, 1)) / 864e5);
    const schalt = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
    return schalt && i >= 59 ? i - 1 : i;
  }

  function tooltip(box) {
    const t = document.createElement("div");
    t.className = "dm-tip";
    t.hidden = true;
    box.appendChild(t);
    return {
      show(html, x, y) {
        t.innerHTML = html;
        t.hidden = false;
        const bw = box.clientWidth, tw = t.offsetWidth;
        t.style.left = Math.max(0, Math.min(bw - tw, x + 14)) + "px";
        t.style.top = Math.max(0, y - t.offsetHeight - 10) + "px";
      },
      hide() { t.hidden = true; },
    };
  }

  function verlauf(box, s) {
    box.textContent = "";
    const leg = document.createElement("ul");
    leg.className = "dm-legende";
    leg.innerHTML = '<li><i style="border-color:var(--s-loess)"></i>Lössboden</li>' +
      '<li><i style="border-color:var(--s-sand)"></i>Sandboden</li>' +
      '<li><i class="band"></i>übliche Spanne</li><li><i class="median"></i>mittlerer Wert</li>';
    box.appendChild(leg);

    const W = Math.max(320, box.clientWidth || 720), H = Math.round(Math.min(300, Math.max(220, W * 0.42))), m = { l: 34, r: 76, t: 12, b: 26 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const start = new Date(s.start + "T00:00:00Z");
    const n = s.reihe_loess.length;
    const tage = Array.from({ length: n }, (_, k) => new Date(start.getTime() + k * 864e5));
    const band = tage.map((d) => s.band[tagIndex(d)]);
    const alle = s.reihe_loess.concat(s.reihe_sand, band.map((b) => b[2])).filter((v) => v != null);
    const ymax = Math.max(120, Math.ceil(Math.max(...alle) / 20) * 20);
    const X = (k) => m.l + (k / (n - 1)) * iw;
    const Y = (v) => m.t + ih - (v / ymax) * ih;

    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
      "aria-label": `Bodenfeuchte bei ${s.name} in den letzten 12 Monaten, Löss- und Sandboden, mit üblicher Spanne` }, box);
    for (let v = 0; v <= ymax; v += 20) {
      el("line", { x1: m.l, x2: m.l + iw, y1: Y(v), y2: Y(v), stroke: v ? "var(--dm-grid)" : "var(--dm-axis)", "stroke-width": 1 }, svg);
      el("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = v + (v === ymax ? " %" : "");
    }
    tage.forEach((d, k) => {
      if (d.getUTCDate() === 1) {
        el("line", { x1: X(k), x2: X(k), y1: m.t + ih, y2: m.t + ih + 4, stroke: "var(--dm-axis)" }, svg);
        if (W < 500 && d.getUTCMonth() % 2 === 1) return; // schmal: nur jeden zweiten Monat beschriften
        const t = el("text", { x: X(k) + 3, y: H - 8 }, svg);
        t.textContent = d.getUTCMonth() === 0 ? String(d.getUTCFullYear()) : MON[d.getUTCMonth()];
      }
    });
    // übliche Spanne
    let pfad = band.map((b, k) => `${k ? "L" : "M"}${X(k).toFixed(1)},${Y(b[2]).toFixed(1)}`).join("");
    for (let k = n - 1; k >= 0; k--) pfad += `L${X(k).toFixed(1)},${Y(band[k][0]).toFixed(1)}`;
    el("path", { d: pfad + "Z", fill: "var(--dm-band)" }, svg);
    el("path", { d: band.map((b, k) => `${k ? "L" : "M"}${X(k).toFixed(1)},${Y(b[1]).toFixed(1)}`).join(""),
      fill: "none", stroke: "var(--dm-median)", "stroke-width": 1.5, "stroke-dasharray": "5 4" }, svg);
    // Trockenstress-Schwelle
    el("line", { x1: m.l, x2: m.l + iw, y1: Y(30), y2: Y(30), stroke: "var(--dm-kritisch)", "stroke-width": 1, "stroke-dasharray": "3 3" }, svg);
    el("text", { x: m.l + iw + 6, y: Y(30) + 4, style: "fill:var(--dm-kritisch)" }, svg).textContent = "Trockenstress";

    const serien = [
      { name: "Lössboden", farbe: "var(--s-loess)", werte: s.reihe_loess },
      { name: "Sandboden", farbe: "var(--s-sand)", werte: s.reihe_sand },
    ];
    const enden = [];
    serien.forEach((se) => {
      let d = "", an = false;
      se.werte.forEach((v, k) => {
        if (v == null) { an = false; return; }
        d += `${an ? "L" : "M"}${X(k).toFixed(1)},${Y(v).toFixed(1)}`;
        an = true;
      });
      el("path", { d, fill: "none", stroke: se.farbe, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
      const letzter = se.werte.length - 1 - [...se.werte].reverse().findIndex((v) => v != null);
      enden.push({ se, y: Y(se.werte[letzter]) });
    });
    enden.sort((a, b) => a.y - b.y);
    for (let i = 1; i < enden.length; i++) if (enden[i].y - enden[i - 1].y < 14) enden[i].y = enden[i - 1].y + 14;
    enden.forEach((e) => { el("text", { x: m.l + iw + 6, y: e.y + 4, class: "lbl" }, svg).textContent = e.se.name; });

    const kreuz = el("line", { y1: m.t, y2: m.t + ih, stroke: "var(--dm-axis)", "stroke-width": 1, visibility: "hidden" }, svg);
    const punkte = serien.map((se) => el("circle", { r: 4.5, fill: se.farbe, stroke: "var(--card)", "stroke-width": 2, visibility: "hidden" }, svg));
    const flaeche = el("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" }, svg);
    const tip = tooltip(box);
    function zeigen(ev) {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      const k = Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / iw) * (n - 1))));
      kreuz.setAttribute("x1", X(k)); kreuz.setAttribute("x2", X(k)); kreuz.setAttribute("visibility", "visible");
      serien.forEach((se, i) => {
        const v = se.werte[k];
        punkte[i].setAttribute("visibility", v == null ? "hidden" : "visible");
        if (v != null) { punkte[i].setAttribute("cx", X(k)); punkte[i].setAttribute("cy", Y(v)); }
      });
      const b = band[k];
      tip.show(`<b>${datumDe(tage[k])}</b>` +
        serien.map((se) => `<span class="sw" style="background:${se.farbe}"></span>${se.name}: ${fmt(se.werte[k])} % nFK`).join("<br>") +
        `<br>üblich: ${b[1]} % (Spanne ${b[0]}–${b[2]} %)`,
        (X(k) / W) * r.width, (Math.min(...serien.map((se) => Y(se.werte[k] ?? b[1]))) / H) * r.height);
    }
    flaeche.addEventListener("pointermove", zeigen);
    flaeche.addEventListener("pointerdown", zeigen);
    flaeche.addEventListener("pointerleave", () => {
      tip.hide(); kreuz.setAttribute("visibility", "hidden"); punkte.forEach((p) => p.setAttribute("visibility", "hidden"));
    });
  }

  function jahre(box, s, aktuellesJahr) {
    box.textContent = "";
    const W = Math.max(320, box.clientWidth || 720), H = Math.round(Math.min(240, Math.max(180, W * 0.33))), m = { l: 34, r: 10, t: 12, b: 26 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const daten = s.stress;
    const ymax = Math.max(20, Math.ceil(Math.max(...daten.map((d) => d[1])) / 20) * 20);
    const schritt = iw / daten.length, bw = Math.max(4, schritt - 2);
    const Y = (v) => m.t + ih - (v / ymax) * ih;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Tage mit Trockenstress je Jahr bei ${s.name}` }, box);
    const tickAbstand = ymax > 100 ? 40 : 20;
    for (let v = 0; v <= ymax; v += tickAbstand) {
      el("line", { x1: m.l, x2: m.l + iw, y1: Y(v), y2: Y(v), stroke: v ? "var(--dm-grid)" : "var(--dm-axis)", "stroke-width": 1 }, svg);
      el("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = v;
    }
    const tip = tooltip(box);
    daten.forEach(([jahr, tage], i) => {
      const x = m.l + i * schritt + (schritt - bw) / 2;
      if (tage > 0) {
        const h = ih - (Y(tage) - m.t), r = Math.min(4, bw / 2, h);
        const y = Y(tage);
        el("path", { d: `M${x},${m.t + ih}V${y + r}Q${x},${y} ${x + r},${y}H${x + bw - r}Q${x + bw},${y} ${x + bw},${y + r}V${m.t + ih}Z`,
          fill: "var(--s-loess)", "fill-opacity": jahr === aktuellesJahr ? 0.45 : 1 }, svg);
      }
      if (jahr % (W < 500 ? 10 : 5) === 0 || (jahr === aktuellesJahr && jahr % 5 >= 3)) {
        el("text", { x: x + bw / 2, y: H - 8, "text-anchor": "middle" }, svg).textContent = jahr;
      }
      const hit = el("rect", { x: m.l + i * schritt, y: m.t, width: schritt, height: ih, fill: "transparent" }, svg);
      const zeigen = () => {
        const r = svg.getBoundingClientRect();
        tip.show(`<b>${jahr}${jahr === aktuellesJahr ? " (bisher)" : ""}</b>${tage} Tage mit Trockenstress`,
          ((x + bw / 2) / W) * r.width, (Y(tage) / H) * r.height);
      };
      hit.addEventListener("pointerenter", zeigen);
      hit.addEventListener("pointerdown", zeigen);
      hit.addEventListener("pointerleave", tip.hide);
    });
  }

  async function start() {
    const boxV = document.getElementById("dm-chart-verlauf");
    const boxJ = document.getElementById("dm-chart-jahre");
    if (!boxV) return;
    let daten;
    try {
      daten = await (await fetch("/duerre/data.json")).json();
    } catch (err) {
      boxV.textContent = "Die Grafik konnte nicht geladen werden. Die Werte stehen in der Tabelle unten.";
      return;
    }
    const jahr = Number(daten.stand.slice(0, 4));
    const knoepfe = document.querySelectorAll(".dm-filter button");
    function waehlen(id) {
      const s = daten.stationen.find((x) => String(x.id) === String(id)) || daten.stationen[0];
      knoepfe.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.station === String(s.id))));
      verlauf(boxV, s);
      if (boxJ) jahre(boxJ, s, jahr);
    }
    let aktiv = daten.stationen[0].id;
    knoepfe.forEach((b) => b.addEventListener("click", () => { aktiv = b.dataset.station; waehlen(aktiv); }));
    waehlen(aktiv);
    let breite = boxV.clientWidth, timer;
    window.addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { if (boxV.clientWidth !== breite) { breite = boxV.clientWidth; waehlen(aktiv); } }, 150);
    });
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
