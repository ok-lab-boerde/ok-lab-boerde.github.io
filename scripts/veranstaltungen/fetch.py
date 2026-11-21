"""Lädt Veranstaltungen aus öffentlichen Kalendern im Landkreis Börde nach scripts/veranstaltungen/.cache/termine.json.

Quellen (Stufe 1, nur Seiten ohne Sperre in robots.txt):
- Landkreis Börde: https://www.landkreis-boerde.de/erleben/veranstaltungen (Liste + Detailseite + ICS je Termin)
- Verwaltungsportal-Gemeinden (Niedere Börde, VG Obere Aller, VG Elbe-Heide): Liste /veranstaltungen,
  Detailseite mit schema.org-Event (Datum, Uhrzeit, Ort)
- Stadt Wanzleben-Börde: Terminübersicht unter /de/aktuelles/veranstaltungen.html (Freitext) und
  öffentliche Sitzungen aus dem Ratsinformationssystem

Übernommen werden nur Fakten (Titel, Datum, Uhrzeit, Ort, Veranstalter, Link), keine Beschreibungen oder Bilder.
Mindestens 2 Sekunden Pause zwischen Abrufen, bei Wanzleben-Börde 15 Sekunden (Crawl-delay).
Nur Standardbibliothek.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
CACHE = HIER / ".cache"
DETAILS = CACHE / "details"
UA = {"User-Agent": "ok-lab-boerde-veranstaltungen/0.1 (+https://ok-lab-boerde.github.io/veranstaltungen/)"}
LK = "https://www.landkreis-boerde.de"
PORTALE = {  # Basis-URL: Gemeinde bzw. Verbandsgemeinde, die das Portal betreibt
    "https://www.niedere-boerde.de": "Niedere Börde",
    "https://www.obere-aller.de": "VG Obere Aller",
    "https://www.elbe-heide.de": "VG Elbe-Heide",
}
WZ = "https://www.wanzleben-boerde.de"
WZ_RIS = "https://ratsinfo.kitu-genossenschaft.de/wzl_bi/"
DETAIL_ALTER = timedelta(days=3)     # Detailseiten so lange aus dem Cache

_letzter: dict[str, float] = {}


def hole(url: str, pause: float = 2.0) -> str:
    host = urllib.parse.urlsplit(url).netloc
    warte = pause - (time.monotonic() - _letzter.get(host, 0.0))
    if warte > 0:
        time.sleep(warte)
    teile = urllib.parse.urlsplit(url)
    url = urllib.parse.urlunsplit(teile._replace(path=urllib.parse.quote(teile.path, safe="/%"),
                                                 query=urllib.parse.quote(teile.query, safe="=&%")))
    req = urllib.request.Request(url, headers=UA)
    for versuch in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                roh = r.read()
            break
        except OSError as ex:
            if versuch == 2:
                raise
            print(f"  {url}: {ex} – neuer Versuch", file=sys.stderr)
            time.sleep(20 * (versuch + 1))
    _letzter[host] = time.monotonic()
    try:
        return roh.decode("utf-8")
    except UnicodeDecodeError:
        return roh.decode("cp1252", errors="replace")


def text(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("​", "").replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", z).strip() for z in s.split("\n")).strip()


def detail(url: str, pause: float = 2.0) -> str:
    """Detailseite mit Cache (Dateiname aus der URL)."""
    DETAILS.mkdir(parents=True, exist_ok=True)
    f = DETAILS / (re.sub(r"[^A-Za-z0-9]+", "_", url.split("//", 1)[1])[:150] + ".html")
    if f.exists() and datetime.now().timestamp() - f.stat().st_mtime < DETAIL_ALTER.total_seconds():
        return f.read_text(encoding="utf-8")
    s = hole(url, pause)
    f.write_text(s, encoding="utf-8")
    return s


# ---------------------------------------------------------------- Landkreis
def ics_zeit(wert: str) -> str:
    """ICS-Zeit (UTC mit Z oder lokal) -> lokale Zeit 'YYYY-MM-DDTHH:MM' bzw. 'YYYY-MM-DD'."""
    if re.fullmatch(r"\d{8}", wert):
        return f"{wert[:4]}-{wert[4:6]}-{wert[6:]}"
    dt = datetime.strptime(wert.rstrip("Z"), "%Y%m%dT%H%M%S")
    if wert.endswith("Z"):
        dt = dt.replace(tzinfo=timezone.utc).astimezone(berlin_offset(dt)).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M")


def berlin_offset(dt_utc: datetime) -> timezone:
    """MEZ/MESZ ohne zoneinfo-Daten (unter Windows fehlt tzdata): letzter Sonntag im März/Oktober, 01:00 UTC."""
    j = dt_utc.year
    def letzter_sonntag(monat: int) -> datetime:
        d = datetime(j, monat, 31)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    beginn = letzter_sonntag(3).replace(hour=1)
    ende = letzter_sonntag(10).replace(hour=1)
    return timezone(timedelta(hours=2 if beginn <= dt_utc < ende else 1))


def landkreis() -> list[dict]:
    s = hole(f"{LK}/erleben/veranstaltungen")
    pfade = list(dict.fromkeys(re.findall(r'href="(/erleben/veranstaltungen/details/termin/[^"?#]+)"', s)))
    out = []
    for p in pfade:
        try:
            ics = hole(f"{LK}{p}.ics")
            seite = detail(f"{LK}{p}")
        except OSError as ex:
            print(f"Landkreis {p}: {ex}", file=sys.stderr)
            continue
        ics = re.sub(r"\r?\n[ \t]", "", ics)          # Zeilenfortsetzung auflösen
        feld = lambda k: (re.search(rf"^{k}[^:\n]*:(.*)$", ics, re.M) or [None, ""])[1].strip()
        titel = feld("SUMMARY").replace("\\,", ",")
        if not titel or not feld("DTSTART"):
            continue
        # "Auf einen Blick": Titel, Zeit, Ort, Straße, PLZ Ort
        blick = ""
        m = re.search(r"Auf einen Blick(.*?)(Zurück|Termin als ICS)", text(seite), re.S)
        if m:
            blick = m.group(1)
        zeilen = [z.strip() for z in blick.split("\n") if z.strip()]
        plz = next((i for i, z in enumerate(zeilen) if re.fullmatch(r"\d{5}", z) or re.match(r"\d{5} ", z)), None)
        adresse = " ".join(zeilen[max(0, plz - 2):plz + 2]) if plz is not None else ""
        out.append({"quelle": "landkreis", "id": "lk-" + p.rsplit("/", 1)[1], "titel": titel,
                    "start": ics_zeit(feld("DTSTART")), "ende": ics_zeit(feld("DTEND")) if feld("DTEND") else "",
                    "ort": feld("LOCATION").replace("\\,", ","), "adresse": adresse, "veranstalter": "",
                    "url": f"{LK}{p}", "gebiet": ""})
    print(f"Landkreis: {len(out)} Termine", file=sys.stderr)
    return out


# ---------------------------------------------------------------- Verwaltungsportal
def portal(basis: str, gebiet: str) -> list[dict]:
    s = hole(f"{basis}/veranstaltungen")
    pfade = {}
    for m in re.finditer(r'href="(?:https?://[^/"]+)?(/veranstaltungen/(\d+)/(\d{4})/(\d\d)/(\d\d)/[^"]*)"', s):
        pfade.setdefault(m.group(2), (m.group(1), f"{m.group(3)}-{m.group(4)}-{m.group(5)}"))
    out = []
    for nr, (pfad, tag) in sorted(pfade.items()):
        start, ende, ort, titel, veranst = tag, "", "", "", ""
        try:
            d = detail(f"{basis}{pfad}")
            for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', d, re.S):
                j = json.loads(blob)
                if j.get("@type") == "Event":
                    sd = j.get("startDate", "")
                    start = sd[:16] if "T" in sd and sd[11:16] != "00:00" else sd[:10] or tag
                    ed = j.get("endDate", "")
                    ende = (ed[:16] if "T" in ed and ed[11:16] != "00:00" else ed[:10]) if ed else ""
                    ort = text((j.get("location") or {}).get("name", "")) if isinstance(j.get("location"), dict) else ""
                    titel = text(j.get("name", ""))
            m = re.search(r"\nVeranstalter\n+([^\n]+)", text(d))
            veranst = m.group(1).strip() if m else ""
            if not titel:
                h = re.search(r"<h1[^>]*>(.*?)</h1>", d, re.S)
                titel = text(h.group(1)) if h else ""
        except (OSError, ValueError) as ex:
            print(f"Portal {pfad}: {ex}", file=sys.stderr)
        if titel:
            out.append({"quelle": "portal", "id": f"vp-{nr}", "titel": titel, "start": start, "ende": ende, "ort": ort,
                        "adresse": "", "veranstalter": veranst, "url": f"{basis}{pfad}", "gebiet": gebiet})
    print(f"{gebiet}: {len(out)} Termine", file=sys.stderr)
    return out


# ---------------------------------------------------------------- Wanzleben-Börde
ZEIT = re.compile(r"(\d{1,2})[:.](\d\d)(?:\s*(?:-|–|bis)\s*(\d{1,2})[:.](\d\d))?")


def wanzleben_text() -> list[dict]:
    url = f"{WZ}/de/aktuelles/veranstaltungen.html"
    s = hole(url, 15)
    m = re.search(r'<h1 class="title">Veranstaltungen</h1>(.*?)article-date', s, re.S)
    if not m:
        print("Wanzleben: Terminübersicht nicht gefunden", file=sys.stderr)
        return []
    roh = re.sub(r"</(p|h\d|div)>", "\n", m.group(1))
    zeilen = [z for z in text(roh).split("\n") if z.strip()]
    out, akt = [], None
    for z in zeilen:
        d = re.match(r"(\d\d)\.(\d\d)\.(\d{4})(.*)", z)
        if d:
            tag = f"{d.group(3)}-{d.group(2)}-{d.group(1)}"
            zt = ZEIT.search(d.group(4))
            start = f"{tag}T{int(zt.group(1)):02d}:{zt.group(2)}" if zt else tag
            ende = f"{tag}T{int(zt.group(3)):02d}:{zt.group(4)}" if zt and zt.group(3) else ""
            akt = {"quelle": "wanzleben", "id": "", "titel": "", "start": start, "ende": ende, "ort": "", "adresse": "",
                   "veranstalter": "", "url": url, "gebiet": "Wanzleben-Börde"}
            out.append(akt)
        elif akt is not None and re.fullmatch(r"(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)", z):
            akt = None
        elif akt is not None:
            if not akt["titel"]:
                akt["titel"] = z
            elif not akt["ort"]:
                akt["ort"] = z
    out = [x for x in out if x["titel"]]
    for x in out:
        x["id"] = "wz-" + re.sub(r"[^a-z0-9]+", "-", f"{x['start']}-{x['titel']}".lower())[:80]
    print(f"Wanzleben-Börde (Übersicht): {len(out)} Termine", file=sys.stderr)
    return out


def wanzleben_sitzungen() -> list[dict]:
    heute = date.today()
    out = []
    for jahr in sorted({heute.year, (heute + timedelta(days=120)).year}):
        s = hole(f"{WZ_RIS}si0046.asp?__cjahr={jahr}&__cmonat=1&__canz=12", 3)
        for zeile in re.findall(r"<tr class=\"smc-t-r-l\">(.*?)</tr>", s, re.S):
            m = re.search(r'<a\s+href="si0057\.asp\?__ksinr=(\d+)"\s+title="Details anzeigen: ([^"]*?) (\d\d)\.(\d\d)\.(\d{4})"', zeile)
            if not m:
                continue
            nr, gremium, t, mo, j = m.groups()
            gremium = html.unescape(gremium).strip()
            if gremium.startswith("Fraktion"):
                continue
            tag = f"{j}-{mo}-{t}"
            if tag < heute.isoformat():
                continue
            infos = [text(x) for x in re.findall(r'<li class="list-inline-item">(.*?)</li>', zeile, re.S)]
            zt = ZEIT.search(infos[0]) if infos else None
            out.append({"quelle": "ratsinfo", "id": f"si-{nr}", "titel": f"Sitzung: {gremium}",
                        "start": f"{tag}T{int(zt.group(1)):02d}:{zt.group(2)}" if zt else tag, "ende": "",
                        "ort": infos[1] if len(infos) > 1 else "", "adresse": "", "veranstalter": "Stadt Wanzleben-Börde",
                        "url": f"{WZ_RIS}si0057.asp?__ksinr={nr}", "gebiet": "Wanzleben-Börde", "art": "sitzung"})
    print(f"Wanzleben-Börde (Sitzungen): {len(out)} Termine", file=sys.stderr)
    return out


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    alle: list[dict] = []
    quellen = [("Landkreis", landkreis), ("Wanzleben-Börde", wanzleben_text), ("Ratsinfo Wanzleben-Börde", wanzleben_sitzungen)]
    quellen += [(g, (lambda b=b, g=g: portal(b, g))) for b, g in PORTALE.items()]
    status = {}
    for name, f in quellen:
        try:
            neu = f()
            alle += neu
            status[name] = len(neu)
        except Exception as ex:  # noqa: BLE001 – eine kaputte Quelle soll die anderen nicht aufhalten
            print(f"{name}: FEHLER {ex}", file=sys.stderr)
            status[name] = None
    # Fällt eine Quelle aus, ihre letzten bekannten Termine behalten
    alt_datei = CACHE / "termine.json"
    if alt_datei.exists():
        alt = json.loads(alt_datei.read_text(encoding="utf-8"))
        kaputt = {n for n, v in status.items() if v is None}
        quelle_von = {"Landkreis": "landkreis", "Wanzleben-Börde": "wanzleben", "Ratsinfo Wanzleben-Börde": "ratsinfo"}
        for x in alt.get("termine", []):
            name = x["gebiet"] if x["quelle"] == "portal" else next((n for n, q in quelle_von.items() if q == x["quelle"]), "")
            if name in kaputt:
                alle.append(x)
    alle.sort(key=lambda x: (x["start"], x["id"]))
    alt_datei.write_text(json.dumps({"abruf": date.today().isoformat(), "quellen": status, "termine": alle},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(alle)} Termine gesamt", file=sys.stderr)


if __name__ == "__main__":
    main()
