/* Betriebe-Karte: Suche, Filter nach Ort und Branche, "jetzt geöffnet", Liste. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("de-DE");
  const SEITE = 50;
  let D, map, cluster, markers, anzeigen = SEITE;

  const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");

  function filtern() {
    const q = norm($("q").value.trim()), ort = $("f-ort").value, br = $("f-branche").value, offen = $("f-offen").checked;
    const jetzt = new Date();
    return D.liste.filter((b) =>
      (!q || b.suche.includes(q)) && (ort === "" || b.gemeinde === +ort) && (br === "" || b.branche === +br) &&
      (!offen || (b.woche && window.okOffen(b.woche, jetzt))));
  }

  function zeichnen(neu = true) {
    if (neu) anzeigen = SEITE;
    const sel = filtern();
    $("treffer").textContent = `${nf.format(sel.length)} ${sel.length === 1 ? "Betrieb" : "Betriebe"} gefunden`;
    cluster.clearLayers();
    cluster.addLayers(sel.map((b) => markers[b.i]));
    const liste = $("liste");
    liste.innerHTML = "";
    const frag = document.createDocumentFragment();
    sel.slice(0, anzeigen).forEach((b) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = b.url; a.textContent = b.name;
      const info = document.createElement("span");
      info.className = "info";
      info.textContent = `${b.detail} · ${b.ort}`;
      const links = document.createElement("span");
      links.append(a, document.createElement("br"), info);
      li.append(links);
      if (b.woche && window.okOffen(b.woche)) {
        const o = document.createElement("span"); o.className = "offen"; o.textContent = "● geöffnet"; li.append(o);
      }
      frag.append(li);
    });
    liste.append(frag);
    $("mehr").hidden = sel.length <= anzeigen;
    $("mehr").textContent = `Weitere anzeigen (${nf.format(sel.length - Math.min(anzeigen, sel.length))})`;
    if (neu && sel.length && ($("f-ort").value !== "" || $("q").value)) {
      map.fitBounds(L.latLngBounds(sel.map((b) => [b.lat, b.lon])), { padding: [20, 20], maxZoom: 15 });
    }
  }

  function init(raw, stand, grenze) {
    const f = Object.fromEntries(raw.felder.map((k, i) => [k, i]));
    D = {
      branchen: raw.branchen, gemeinden: raw.gemeinden,
      liste: raw.betriebe.map((r, i) => ({
        i, name: r[f.name], branche: r[f.branche], detail: r[f.detail], lat: r[f.lat], lon: r[f.lon],
        gemeinde: r[f.gemeinde], ort: r[f.ort], url: r[f.url], woche: r[f.woche],
        suche: norm(`${r[f.name]} ${r[f.detail]} ${r[f.ort]} ${raw.branchen[r[f.branche]][1]}`),
      })),
    };
    const d = new Date(stand.datenstand + "T00:00:00").toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });
    $("stand").textContent = `${nf.format(D.liste.length)} Betriebe in ${stand.gemeinden} Gemeinden · Datenstand ${d} · wöchentlich aktualisiert`;
    $("f-ort").insertAdjacentHTML("beforeend", D.gemeinden.map(([, n], i) => `<option value="${i}">${n.replace(/</g, "")}</option>`).join(""));
    $("f-branche").insertAdjacentHTML("beforeend", D.branchen.map(([, n], i) => `<option value="${i}">${n.replace(/</g, "")}</option>`).join(""));

    map = L.map("karte", { scrollWheelZoom: false, preferCanvas: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap-Mitwirkende</a>',
    }).addTo(map);
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    map.on("click focus", () => map.scrollWheelZoom.enable());
    const g = L.geoJSON(grenze, { style: { color: "#0d4a8f", weight: 2.5, fill: false, dashArray: "6 4" }, interactive: false }).addTo(map);
    map.fitBounds(g.getBounds(), { padding: [8, 8] });
    cluster = L.markerClusterGroup({
      showCoverageOnHover: false, maxClusterRadius: 45, chunkedLoading: true,
      iconCreateFunction: (c) => { const n = c.getChildCount(), s = n < 10 ? 28 : n < 100 ? 34 : 42;
        return L.divIcon({ html: `<div class="cluster" style="width:${s}px;height:${s}px">${n}</div>`, className: "", iconSize: [s, s] }); },
    }).addTo(map);
    markers = D.liste.map((b) => {
      const m = L.circleMarker([b.lat, b.lon], { radius: 6, color: "#fff", weight: 1.5, fillColor: "#0d4a8f", fillOpacity: 0.95 });
      m.bindPopup(() => {
        const box = document.createElement("div");
        const a = document.createElement("a"); a.href = b.url; a.textContent = b.name; a.style.fontWeight = "700";
        const t = document.createElement("div"); t.textContent = `${b.detail} · ${b.ort}`;
        box.append(a, t);
        return box;
      });
      return m;
    });

    let t;
    $("q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => zeichnen(), 200); });
    ["f-ort", "f-branche", "f-offen"].forEach((id) => $(id).addEventListener("change", () => zeichnen()));
    $("suche").addEventListener("submit", (ev) => ev.preventDefault());
    $("mehr").addEventListener("click", () => { anzeigen += SEITE; zeichnen(false); });
    zeichnen();
  }

  Promise.all(["/betriebe/data/betriebe.json", "/betriebe/data/stand.json", "/unfallatlas/data/kreisgrenze.geojson"].map((u) =>
    fetch(u, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error(u); return r.json(); })))
    .then(([raw, stand, grenze]) => init(raw, stand, grenze))
    .catch(() => { $("stand").textContent = "Die Daten konnten nicht geladen werden. Bitte später erneut versuchen."; });
})();
