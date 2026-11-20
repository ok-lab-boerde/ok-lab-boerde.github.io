/* Unfallatlas Börde – Karte, Filter und Diagramme. Keine externen Abhängigkeiten außer Leaflet (lokal). */
(() => {
  "use strict";

  const KAT = { 1: "Getötete", 2: "Schwerverletzte", 3: "Leichtverletzte" };
  const KAT_TEXT = { 1: "Unfall mit Getöteten", 2: "Unfall mit Schwerverletzten", 3: "Unfall mit Leichtverletzten" };
  const KAT_FARBE = { 1: "#8b1a1a", 2: "#e0532f", 3: "#f2a33a" };
  const KAT_RADIUS = { 1: 8, 2: 6, 3: 4.5 };
  const ART = {
    0: "Unfall anderer Art", 1: "Zusammenstoß mit anfahrendem/anhaltendem/ruhendem Fahrzeug",
    2: "Zusammenstoß mit vorausfahrendem/wartendem Fahrzeug", 3: "Zusammenstoß mit seitlich in gleicher Richtung fahrendem Fahrzeug",
    4: "Zusammenstoß mit entgegenkommendem Fahrzeug", 5: "Zusammenstoß mit einbiegendem/kreuzendem Fahrzeug",
    6: "Zusammenstoß zwischen Fahrzeug und Fußgänger:in", 7: "Aufprall auf Fahrbahnhindernis",
    8: "Abkommen von der Fahrbahn nach rechts", 9: "Abkommen von der Fahrbahn nach links",
  };
  const LICHT = { 0: "Tageslicht", 1: "Dämmerung", 2: "Dunkelheit" };
  const MONAT = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];
  const TAG_NAME = { 1: "Sonntag", 2: "Montag", 3: "Dienstag", 4: "Mittwoch", 5: "Donnerstag", 6: "Freitag", 7: "Samstag" };
  const TAG_REIHE = [2, 3, 4, 5, 6, 7, 1]; // Montag zuerst
  const TAG_KURZ = { 1: "So", 2: "Mo", 3: "Di", 4: "Mi", 5: "Do", 6: "Fr", 7: "Sa" };
  const BET = [["rad", "Fahrrad"], ["fuss", "Fußgänger:in"], ["pkw", "Pkw"], ["krad", "Kraftrad"], ["gkfz", "Lkw"], ["sonstige", "Sonstige"]];

  const nf = new Intl.NumberFormat("de-DE");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const $ = (id) => document.getElementById(id);

  let D, BITS, F, map, clusterLayer, heatLayer, markers;

  // ---------- Daten ----------
  function prepare(raw) {
    F = Object.fromEntries(raw.felder.map((f, i) => [f, i]));
    BITS = raw.bits;
    return raw.unfaelle.map((u, i) => ({
      i, jahr: u[F.jahr], monat: u[F.monat], tag: u[F.wochentag], std: u[F.stunde], kat: u[F.kategorie],
      art: u[F.art], licht: u[F.licht], b: u[F.beteiligt], gem: u[F.gemeinde], lat: u[F.lat], lon: u[F.lon],
    }));
  }
  const hat = (u, key) => (u.b & BITS[key]) !== 0;

  function filterState() {
    return {
      von: +$("f-von").value, bis: +$("f-bis").value,
      kat: new Set([...document.querySelectorAll('input[name="kat"]:checked')].map((e) => +e.value)),
      bet: $("f-bet").value, licht: $("f-licht").value, rad: $("f-rad").checked,
      ansicht: document.querySelector('input[name="ansicht"]:checked').value,
    };
  }

  function apply(list, s) {
    return list.filter((u) =>
      u.jahr >= s.von && u.jahr <= s.bis && s.kat.has(u.kat) &&
      (!s.bet || hat(u, s.bet)) && (s.licht === "" || u.licht === +s.licht) && (!s.rad || hat(u, "rad")));
  }

  // ---------- Karte ----------
  function popup(u) {
    const bet = BET.filter(([k]) => hat(u, k)).map(([, n]) => n);
    const lkwHinweis = hat(u, "gkfz_unbekannt") ? "<br><small>2017: Lkw sind unter „Sonstige“ erfasst</small>" : "";
    return `<b>${esc(KAT_TEXT[u.kat])}</b>` +
      `${esc(TAG_NAME[u.tag])}, ${esc(MONAT[u.monat])} ${u.jahr}, ${u.std}–${u.std + 1} Uhr<br>` +
      `${esc(ART[u.art] ?? "unbekannt")}<br>` +
      `Licht: ${esc(LICHT[u.licht] ?? "unbekannt")}<br>` +
      `Beteiligt: ${esc(bet.join(", ") || "keine Angabe")}${lkwHinweis}<br>` +
      `Gemeinde: ${esc(D.gemeinden[u.gem] ?? u.gem)}`;
  }

  function initMap(grenze) {
    map = L.map("map", { scrollWheelZoom: false, keyboard: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
    }).addTo(map);
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    map.attributionControl.addAttribution('Unfälle: <a href="https://unfallatlas.statistikportal.de/">Unfallatlas</a> · Grenze: © GeoBasis-DE / BKG');
    const g = L.geoJSON(grenze, { style: { color: "#0d4a8f", weight: 2.5, fill: false, dashArray: "6 4" }, interactive: false }).addTo(map);
    map.fitBounds(g.getBounds(), { padding: [10, 10] });
    map.on("focus", () => map.scrollWheelZoom.enable());
    map.on("blur", () => map.scrollWheelZoom.disable());
    map.on("click", () => map.scrollWheelZoom.enable());

    const legend = L.control({ position: "bottomright" });
    legend.onAdd = () => {
      const div = L.DomUtil.create("div", "map-legend");
      div.innerHTML = [1, 2, 3].map((k) =>
        `<div><span class="dot" style="width:${KAT_RADIUS[k] * 2}px;height:${KAT_RADIUS[k] * 2}px;background:${KAT_FARBE[k]}"></span>${KAT[k]}</div>`).join("") +
        '<div><span class="dot" style="width:14px;height:14px;background:rgba(13,74,143,.85)"></span>Gruppe (Anzahl)</div>';
      return div;
    };
    legend.addTo(map);

    clusterLayer = L.markerClusterGroup({
      showCoverageOnHover: false, maxClusterRadius: 45, spiderfyOnMaxZoom: true, chunkedLoading: true,
      iconCreateFunction: (c) => {
        const n = c.getChildCount(), s = n < 10 ? 28 : n < 100 ? 34 : 42;
        return L.divIcon({ html: `<div class="cluster" style="width:${s}px;height:${s}px">${n}</div>`, className: "", iconSize: [s, s] });
      },
    });
    markers = D.list.map((u) => L.circleMarker([u.lat, u.lon], {
      radius: KAT_RADIUS[u.kat], color: "#fff", weight: 1.5, fillColor: KAT_FARBE[u.kat], fillOpacity: 0.95,
    }).bindPopup(() => popup(u)));
    heatLayer = L.heatLayer([], { radius: 16, blur: 18, maxZoom: 13, minOpacity: 0.3 });
  }

  function updateMap(sel, ansicht) {
    clusterLayer.clearLayers();
    if (ansicht === "heat") {
      map.removeLayer(clusterLayer);
      heatLayer.setLatLngs(sel.map((u) => [u.lat, u.lon, 1]));
      if (!map.hasLayer(heatLayer)) heatLayer.addTo(map);
    } else {
      if (map.hasLayer(heatLayer)) map.removeLayer(heatLayer);
      // Schwere Unfälle zuletzt einfügen, damit sie oben liegen
      clusterLayer.addLayers([...sel].sort((a, b) => b.kat - a.kat).map((u) => markers[u.i]));
      if (!map.hasLayer(clusterLayer)) clusterLayer.addTo(map);
    }
  }

  // ---------- Diagramme ----------
  const NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }
  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }

  function barChart(id, items, opts = {}) {
    const box = $(id);
    box.innerHTML = "";
    const W = Math.max(box.clientWidth, 260), H = opts.height || 200;
    const m = { t: 18, r: 4, b: 24, l: 36 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const max = niceMax(Math.max(1, ...items.map((d) => d.v)));
    const step = iw / items.length, bw = Math.max(Math.min(step - 2, 48), 2);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.aria || "" }, box);
    for (let i = 0; i <= 4; i++) {
      const v = (max / 4) * i, y = m.t + ih - (v / max) * ih;
      el("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: i ? "var(--grid)" : "var(--axis)", "stroke-width": 1 }, svg);
      el("text", { x: m.l - 6, y: y + 4, "text-anchor": "end", class: "tick" }, svg).textContent = nf.format(v);
    }
    const tip = document.createElement("div");
    tip.className = "tip";
    box.appendChild(tip);
    const showLabels = opts.labels !== false && step >= 26;
    items.forEach((d, i) => {
      const cx = m.l + step * i + step / 2, h = (d.v / max) * ih, x = cx - bw / 2, y = m.t + ih - h;
      const r = Math.min(4, bw / 2, h);
      if (h > 0) {
        el("path", { d: `M${x},${m.t + ih}v-${h - r}a${r},${r} 0 0 1 ${r},-${r}h${bw - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}z`, fill: "var(--bar)" }, svg);
      }
      if (showLabels) el("text", { x: cx, y: y - 4, "text-anchor": "middle", class: "val" }, svg).textContent = nf.format(d.v);
      if (!opts.every || i % opts.every === 0) el("text", { x: cx, y: H - 6, "text-anchor": "middle", class: "tick" }, svg).textContent = d.label;
      const hit = el("rect", { x: m.l + step * i, y: m.t, width: step, height: ih, fill: "transparent" }, svg);
      const show = () => {
        const k = svg.getBoundingClientRect().width / W;
        tip.textContent = `${d.title}: ${nf.format(d.v)} Unfälle`;
        tip.style.display = "block";
        tip.style.left = Math.min(Math.max(cx * k - tip.offsetWidth / 2, 0), box.clientWidth - tip.offsetWidth) + "px";
        tip.style.top = Math.max(y * k - tip.offsetHeight - 8, 0) + "px";
      };
      hit.addEventListener("pointerenter", show);
      hit.addEventListener("pointerdown", show);
      hit.addEventListener("pointerleave", () => { tip.style.display = "none"; });
    });
  }

  function table(id, head, rows) {
    $(id).innerHTML = `<table><thead><tr>${head.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>` +
      rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("") + "</tbody></table>";
  }

  function updateCharts(sel, s) {
    const jahre = D.stand.jahre.filter((j) => j >= s.von && j <= s.bis);
    const perJahr = jahre.map((j) => ({ label: String(j).slice(2), title: String(j), v: sel.filter((u) => u.jahr === j).length }));
    perJahr.forEach((d) => { d.label = jahre.length > 6 ? "’" + d.label : d.title; });
    barChart("c-jahr", perJahr, { aria: "Balkendiagramm: Unfälle pro Jahr" });
    table("t-jahr", ["Jahr", "Unfälle", ...Object.values(KAT)],
      jahre.map((j) => { const x = sel.filter((u) => u.jahr === j); return [j, nf.format(x.length), ...[1, 2, 3].map((k) => nf.format(x.filter((u) => u.kat === k).length))]; }));

    const tage = TAG_REIHE.map((t) => ({ label: TAG_KURZ[t], title: TAG_NAME[t], v: sel.filter((u) => u.tag === t).length }));
    barChart("c-tag", tage, { aria: "Balkendiagramm: Unfälle nach Wochentag" });
    table("t-tag", ["Wochentag", "Unfälle"], tage.map((d) => [d.title, nf.format(d.v)]));

    const std = Array.from({ length: 24 }, (_, h) => ({ label: String(h), title: `${h}:00–${h}:59 Uhr`, v: sel.filter((u) => u.std === h).length }));
    barChart("c-std", std, { aria: "Balkendiagramm: Unfälle nach Uhrzeit", every: $("c-std").clientWidth < 500 ? 3 : 2, height: 220 });
    table("t-std", ["Uhrzeit", "Unfälle"], std.map((d) => [d.title, nf.format(d.v)]));

    const gem = new Map();
    for (const u of sel) {
      const g = gem.get(u.gem) || { n: 0, k1: 0, k2: 0, rad: 0 };
      g.n++; if (u.kat === 1) g.k1++; if (u.kat === 2) g.k2++; if (hat(u, "rad")) g.rad++;
      gem.set(u.gem, g);
    }
    const top = [...gem.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 15);
    table("t-gem", ["Gemeinde", "Unfälle", "mit Getöteten", "mit Schwerverletzten", "mit Fahrrad"],
      top.map(([k, g]) => [D.gemeinden[k] ?? k, nf.format(g.n), nf.format(g.k1), nf.format(g.k2), nf.format(g.rad)]));
    if (!top.length) $("t-gem").innerHTML = "<p>Keine Unfälle in der aktuellen Auswahl.</p>";
  }

  function updateSummary(sel, s) {
    const k = [1, 2, 3].map((x) => sel.filter((u) => u.kat === x).length);
    const zeit = s.von === s.bis ? `im Jahr ${s.von}` : `von ${s.von} bis ${s.bis}`;
    const lkw = s.bet === "gkfz" && s.von <= 2017 ? " Für 2017 gibt es keine getrennten Lkw-Angaben." : "";
    $("summary").innerHTML = `<strong>${nf.format(sel.length)}</strong> Unfälle ${zeit}` +
      `<span class="sev">${[1, 2, 3].map((x, i) => `<span><span class="dot" style="width:${KAT_RADIUS[x] * 1.6}px;height:${KAT_RADIUS[x] * 1.6}px;background:${KAT_FARBE[x]}"></span>${nf.format(k[i])} ${KAT[x]}</span>`).join("")}</span>` +
      (lkw ? `<br><small>${lkw}</small>` : "");
  }

  function update() {
    const s = filterState();
    if (s.von > s.bis) { $("f-bis").value = s.von; s.bis = s.von; }
    const sel = apply(D.list, s);
    updateSummary(sel, s);
    updateMap(sel, s.ansicht);
    updateCharts(sel, s);
  }

  function initFilters() {
    const opts = D.stand.jahre.map((j) => `<option value="${j}">${j}</option>`).join("");
    $("f-von").innerHTML = opts; $("f-bis").innerHTML = opts;
    $("f-von").value = D.stand.jahre[0];
    $("f-bis").value = D.stand.jahre[D.stand.jahre.length - 1];
    $("filters").addEventListener("change", update);
    $("filters").addEventListener("submit", (e) => e.preventDefault());
    $("f-reset").addEventListener("click", () => {
      $("filters").reset();
      $("f-von").value = D.stand.jahre[0];
      $("f-bis").value = D.stand.jahre[D.stand.jahre.length - 1];
      update();
    });
    let t;
    window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => updateCharts(apply(D.list, filterState()), filterState()), 150); });
  }

  Promise.all(["data/unfaelle.json", "data/stand.json", "data/kreisgrenze.geojson"].map((u) =>
    fetch(u, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(u); return r.json(); })))
    .then(([raw, stand, grenze]) => {
      D = { list: prepare(raw), gemeinden: raw.gemeinden, stand };
      const ds = new Date(stand.datenstand + "T00:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });
      $("stand").textContent = `Zeitraum ${stand.jahre[0]}–${stand.jahre[stand.jahre.length - 1]} · ${nf.format(stand.anzahl)} Unfälle · Datenstand der Quelle: ${ds}`;
      initFilters();
      initMap(grenze);
      update();
    })
    .catch(() => {
      $("stand").textContent = "";
      $("summary").innerHTML = '<span class="err">Die Daten konnten nicht geladen werden. Bitte später erneut versuchen.</span>';
    });
})();
