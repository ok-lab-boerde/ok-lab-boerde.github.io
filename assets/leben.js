/* Leben in der Börde: Orte-Tabelle filtern und sortieren. Die Daten stehen als data-Attribute in den Tabellenzeilen. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat("de-DE");

  document.addEventListener("DOMContentLoaded", () => {
    const tbody = $("lb-tabelle").tBodies[0];
    const zeilen = [...tbody.rows].map((tr) => ({
      tr, g: tr.dataset.g, md: +tr.dataset.md, wob: +tr.dataset.wob,
      d: tr.dataset.d.split(",").map((x) => (x === "" ? Infinity : +x)),
      name: tr.cells[0].textContent.trim(),
    }));
    const haken = [...document.querySelectorAll("#lb-filter .haken input[type=checkbox]")];
    const coll = new Intl.Collator("de");

    function anwenden() {
      const g = $("lb-gem").value, md = $("lb-md").value, maxKm = +$("lb-km").value, sort = $("lb-sort").value;
      const pflicht = haken.filter((h) => h.checked).map((h) => +h.value);
      const sortiert = [...zeilen].sort((a, b) =>
        sort === "md" ? a.md - b.md : sort === "wob" ? a.wob - b.wob : coll.compare(a.name, b.name));
      let n = 0;
      const frag = document.createDocumentFragment();
      for (const z of sortiert) {
        const ok = (g === "" || z.g === g) && (md === "" || z.md <= +md) && pflicht.every((i) => z.d[i] <= maxKm);
        z.tr.hidden = !ok;
        if (ok) n++;
        frag.append(z.tr);
      }
      tbody.append(frag);
      $("lb-treffer").textContent = `${nf.format(n)} von ${nf.format(zeilen.length)} Orten`;
    }

    $("lb-filter").addEventListener("change", anwenden);
    $("lb-filter").addEventListener("submit", (ev) => ev.preventDefault());
    anwenden();
  });
})();
