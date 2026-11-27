"""Wahlatlas Börde: Wahlergebnisse der 34 Gemeinden im Landkreis Börde von 1990 bis heute.

Quelle ist das Wahlportal des Statistischen Landesamts Sachsen-Anhalt (wahlergebnisse.sachsen-anhalt.de).
Ältere Gemeindeergebnisse enthalten eine Spalte mit der heutigen Nachfolgegemeinde („AGS 2019“ bzw. „AGS 2014“);
darüber werden alle Wahlen seit 1990 auf die heutigen 34 Gemeinden des Landkreises umgerechnet.

Erzeugt `wahlen/index.html`, `wahlen/<gemeinde>/index.html` und `wahlen/data.json`. Nur Standardbibliothek.

  python scripts/wahlen/build.py              Seiten erzeugen
  python scripts/wahlen/build.py --legenden   Parteinamen der alten Wahlen aus den PDF-Datensatzbeschreibungen
                                              neu einlesen (braucht pdftotext) und in legenden.json speichern

Die Ergebnisse ändern sich nach der Feststellung nicht mehr; das Skript muss nur nach einer neuen Wahl laufen
(dann die Wahl in WAHLEN ergänzen).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "orte"))
from seiten import BASIS_URL, e, seite  # noqa: E402

HIER = Path(__file__).resolve().parent
CACHE = HIER / ".cache"
LEGENDEN = HIER / "legenden.json"
OUT = ROOT / "wahlen"
PORTAL = "https://wahlergebnisse.sachsen-anhalt.de/wahlen"
KREIS = "15083"

# id, Art, Datum, Gemeindedatei, Kreisdatei (amtliches Kreisergebnis mit Briefwahl), Datensatzbeschreibung,
# Gemeindeergebnisse mit Briefwahl?
W = [
    ("lt90", "LT", "1990-10-14", "lt90/and/LT1990_GEM.csv", None, "lt90/and/DSB_LT_1990.pdf", False),
    ("bt90", "BT", "1990-12-02", "bt90/and/BT1990_GEM.csv", None, "bt90/and/DSB_BT_1990.pdf", False),
    ("ew94", "EW", "1994-06-12", "ew94/and/EW1994_GEM.csv", None, "ew94/and/DSB_EW_1994.pdf", False),
    ("lt94", "LT", "1994-06-26", "lt94/and/LT1994_GEM.csv", None, "lt94/and/DSB_LT_1994.pdf", False),
    ("bt94", "BT", "1994-10-16", "bt94/and/BT1994_GEM.csv", None, "bt94/and/DSB_BT_1994.pdf", False),
    ("lt98", "LT", "1998-04-26", "lt98/and/LT1998_GEM.csv", None, "lt98/and/DSB_LT_1998.pdf", False),
    ("bt98", "BT", "1998-09-27", "bt98/and/BT1998_GEM.csv", None, "bt98/and/DSB_BT_1998.pdf", False),
    ("ew99", "EW", "1999-06-13", "ew99/and/EW1999_GEM.csv", None, "ew99/and/DSB_EW_1999.pdf", False),
    ("lt02", "LT", "2002-04-21", "lt02/and/LT2002_GEM.csv", None, "lt02/and/DSB_LT_2002.pdf", False),
    ("bt02", "BT", "2002-09-22", "bt02/and/BT2002_GEM.csv", None, "bt02/and/DSB_BT_2002.pdf", False),
    ("ew04", "EW", "2004-06-13", "ew04/and/EW2004_GEM.csv", None, "ew04/and/DSB_EW_2004.pdf", False),
    ("bt05", "BT", "2005-09-18", "bt05/and/BT2005_GEM.csv", None, "bt05/and/DSB_BT_2005.pdf", False),
    ("lt06", "LT", "2006-03-26", "lt06/and/LT2006_GEM.csv", None, "lt06/and/DSB_LT_2006.pdf", False),
    ("ew09", "EW", "2009-06-07", "ew09/and/EW2009_GEM.csv", "ew09/and/EW2009_LAN_KRS.csv", "ew09/and/DSB_EW_2009.pdf", False),
    ("bt09", "BT", "2009-09-27", "bt09/and/BT2009_GEM.csv", "bt09/and/BT2009_LAN_KRS_WKR.csv", "bt09/and/DSB_BT_2009.pdf", False),
    ("lt11", "LT", "2011-03-20", "lt11/and/LT2011_GEM.csv", "lt11/erg/csv/lt11dat2.csv", "lt11/and/DSB_LT_2011.pdf", False),
    ("bt13", "BT", "2013-09-22", "bt13/and/BT2013_GEM.csv", "bt13/and/BT2013_LAN_KRS_WKR.csv", "bt13/and/DSB_BT_2013.pdf", False),
    ("ew14", "EW", "2014-05-25", "ew14/and/EW2014_GEM.csv", "ew14/and/EW2014_LAN_KRS.csv", "ew14/and/DSB_EW_2014.pdf", False),
    ("lt16", "LT", "2016-03-13", "lt16/erg/csv/LT2016_GEM.csv", "lt16/erg/csv/lt16dat2.csv", "lt16/and/DSB_LT_2016.pdf", False),
    ("bt17", "BT", "2017-09-24", "bt17/and/BT2017_GEM.csv", "bt17/and/BT2017_LAN_KRS_WKR.csv", "bt17/and/DSB_BT_2017.pdf", False),
    ("ew19", "EW", "2019-05-26", "ew19/and/EW2019_GEM.csv", "ew19/and/EW2019_LAN_KRS.csv", "ew19/and/DSB_EW_2019.pdf", False),
    ("lt21", "LT", "2021-06-06", "lt21/erg/csv/lt21dat2.csv", None, None, True),
    ("bt21", "BT", "2021-09-26", "bt21/erg/csv/bt21dat2.csv", None, None, True),
    ("ew24", "EW", "2024-06-09", "ew24/erg/csv/ew24dat3.csv", None, None, True),
    ("bt25", "BT", "2025-02-23", "bt25/erg/csv/bt25dat2.csv", None, None, True),
    ("lt26", "LT", "2026-09-06", "lt26/downloads/Ergebnisse_Gemeinden_LT_2026.csv", None, None, True),
]
ART = {"LT": "Landtagswahl", "BT": "Bundestagswahl", "EW": "Europawahl"}
ART_KURZ = {"LT": "Landtag", "BT": "Bundestag", "EW": "Europa"}
STIMME = {"LT": "Zweitstimmen", "BT": "Zweitstimmen", "EW": "Stimmen"}

# Parteifamilien: über die Jahre gleiche Farbe und vergleichbar (PDS → Linkspartei.PDS → Die Linke)
FAMILIEN = ["CDU", "AfD", "Die Linke", "SPD", "Grüne", "FDP", "DVU", "Freie Wähler", "BSW", "NPD", "REP", "Schill"]
IMMER = {"CDU", "AfD", "Die Linke", "SPD", "Grüne", "FDP", "BSW"}  # immer einzeln, sonst nur ab 3 % im Kreis
SCHWELLE = 3.0
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]


def familie(kurz: str, lang: str = "") -> str | None:
    t = f"{kurz} {lang}"
    k = kurz.strip().rstrip("0123456789").strip()
    if "Christlich Demokratische Union" in t or k == "CDU":
        return "CDU"
    if k == "SPD":
        return "SPD"
    if (k in ("PDS", "Die Linke.", "DIE LINKE", "Die Linke") or "Linkspartei" in t or "Demokratischen Sozialismus" in t
            or "DIE LINKE" in t.upper()):
        return "Die Linke"
    if "Freie Demokratische" in t or k in ("FDP", "F.D.P."):
        return "FDP"
    if k.startswith(("GRÜ", "B90", "BÜ90")) or "GRÜNEN" in t or "Bündnis 90/Grüne" in t or "Grüne Liste" in t:
        return "Grüne"
    if "Alternative für Deutschland" in t or k == "AfD":
        return "AfD"
    if "VOLKSUNION" in t.upper():
        return "DVU"
    if k == "NPD":
        return "NPD"
    if "REPUBLIKANER" in t.upper() or k == "REP":
        return "REP"
    if k == "FREIE WÄHLER" or (t.startswith("FREIE WÄHLER") and "Bürgerinitiativen" not in t):
        return "Freie Wähler"
    if k == "BSW":
        return "BSW"
    if "Rechtsstaatlicher Offensive" in t and "Bündnis" not in t:
        return "Schill"
    return None


def anzeige(fam: str, jahr: int) -> str:
    """Name der Partei zur Zeit der Wahl."""
    if fam == "Die Linke":
        return "PDS" if jahr < 2005 else "Linkspartei.PDS" if jahr < 2007 else "Die Linke"
    if fam == "Grüne" and jahr == 1990:
        return "Bündnis 90/Grüne"
    if fam == "Schill":
        return "Schill-Partei"
    return fam


# ---------------------------------------------------------------- Laden

def holen(pfad: str) -> bytes:
    ziel = CACHE / pfad.replace("/", "_")
    if not ziel.exists():
        req = urllib.request.Request(f"{PORTAL}/{pfad}", headers={"User-Agent": "ok-lab-boerde-wahlatlas"})
        with urllib.request.urlopen(req, timeout=120) as r:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(r.read())
    return ziel.read_bytes()


def text(pfad: str) -> str:
    roh = holen(pfad)
    try:
        return roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        return roh.decode("latin-1")


def legenden_einlesen() -> None:
    """Parteinamen der Spalten Dnn/Fnn aus den PDF-Datensatzbeschreibungen."""
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext fehlt (Paket poppler-utils)")
    alle = {}
    for wid, art, datum, gem, krs, dsb, _ in W:
        if not dsb:
            continue
        holen(dsb)
        pdf = CACHE / dsb.replace("/", "_")
        t = subprocess.run(["pdftotext", "-raw", "-enc", "UTF-8", str(pdf), "-"], capture_output=True,
                           check=True).stdout.decode("utf-8", "replace")
        kopf = [k.strip() for k in text(gem).splitlines()[0].split(";")]
        leg: dict[str, list[str]] = {}
        roh_zeilen = [z.strip() for z in t.splitlines()]
        for n, z in enumerate(roh_zeilen):
            if re.match(r"^[DF]\d\d$", z) and n + 1 < len(roh_zeilen):  # Name in der nächsten Zeile
                z = f"{z} {roh_zeilen[n + 1]}"
            m = re.match(r"^([DF]\d\d)\d? (.+?)(?: [7\-])?$", z)  # \d?: Fußnotenziffer wie „F162“
            if not m:
                continue
            code, rest = m.groups()
            if code in leg:  # Tippfehler in der Beschreibung: nächste freie Spalte derselben Reihe
                frei = [k for k in kopf if k[:1] == code[0] and re.match(r"^[DF]\d\d$", k) and k not in leg and k > code]
                if not frei:
                    continue
                code = frei[0]
            leg[code] = rest
        alle[wid] = leg
    LEGENDEN.write_text(json.dumps(alle, ensure_ascii=False, indent=1), "utf-8")
    print("geschrieben:", LEGENDEN)


def tabelle(pfad: str) -> tuple[list[str], list[list[str]]]:
    zeilen = [z for z in text(pfad).splitlines() if z.strip()]
    kopf = [k.strip().strip('"').strip() for k in zeilen[0].split(";")]
    return kopf, [[x.strip().strip('"').strip() for x in z.split(";")] for z in zeilen[1:]]


def spalte(kopf: list[str], *muster: str) -> int | None:
    for mu in muster:
        for i, k in enumerate(kopf):
            if re.match(mu, k, re.I):
                return i
    return None


def zahl(w: str) -> int:
    w = w.strip()
    return int(w) if w not in ("", "-", ".") else 0


def lesen(wid: str, art: str, pfad: str, legende: dict | None, nur_kreis: bool = False) -> dict[str, dict]:
    """Ergebnisse je heutiger Gemeinde (oder mit nur_kreis die Kreiszeile 15083)."""
    kopf, zeilen = tabelle(pfad)
    i_satz = spalte(kopf, r"^SART$", r"^Satzart$")
    i_schl = spalte(kopf, r"^AGS$", r"^NR$", r"^Schl")
    i_nach = spalte(kopf, r"^AGS\s*20\d\d$")
    i_lokal = spalte(kopf, r"^Wahllokal$")
    i_name = spalte(kopf, r"^Name$")
    i_a = spalte(kopf, r"^A$", r"^A\s*[-.]")
    i_b = spalte(kopf, r"^B$", r"^B\s*[-.]")
    # Zweitstimmen stehen in F; alte Europawahl-Dateien haben nur D (eine Stimme)
    buchst = "F" if spalte(kopf, r"^F$", r"^F\s*[-.]\s*G") is not None else "D"
    i_g = spalte(kopf, rf"^{buchst}$", rf"^{buchst}\s*[-.]\s*G")
    parteien = []
    for i, k in enumerate(kopf):
        m = re.match(rf"^{buchst}(\d\d)(?:\s*[-.]\s*(.+))?$", k)
        if not m:
            continue
        code = f"{buchst}{m.group(1)}"
        if m.group(2):
            kurz, lang = m.group(2).strip(), ""
        elif legende and code in legende:
            kurz, lang = legende[code].split(" ")[0], legende[code]
        else:
            raise SystemExit(f"{wid}: keine Legende für {code}")
        parteien.append((i, kurz.strip(), lang))

    out: dict[str, dict] = {}
    for w in zeilen:
        satz = w[i_satz]
        if nur_kreis:
            if satz != "KRS" or w[i_schl] != KREIS:
                continue
            ziel = KREIS
        else:
            if satz != "GEM":
                continue
            ziel = w[i_nach] if i_nach is not None and w[i_nach] else w[i_schl]
            if not ziel.startswith(KREIS):
                continue
            if i_lokal is not None and w[i_lokal] != "":
                continue
        g = out.setdefault(ziel, {"wb": 0, "waehler": 0, "gueltig": 0, "stimmen": {}, "name": w[i_name] if i_name is not None else ""})
        g["wb"] += zahl(w[i_a])
        g["waehler"] += zahl(w[i_b])
        g["gueltig"] += zahl(w[i_g])
        for i, kurz, lang in parteien:
            fam = familie(kurz, lang)
            schl = fam or kurz.rstrip("0123456789").strip()
            g["stimmen"][schl] = g["stimmen"].get(schl, 0) + zahl(w[i])
        if nur_kreis:
            break
    for ags, g in out.items():
        s = sum(g["stimmen"].values())
        if s != g["gueltig"]:
            raise SystemExit(f"{wid} {ags}: Summe der Parteien {s} ≠ gültige Stimmen {g['gueltig']}")
    return out


# ---------------------------------------------------------------- Aufbereiten

def slug(text_: str) -> str:
    t = text_.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def gemeinde_name(n: str) -> str:
    n = re.sub(r"^(Gemeinde|Stadt|Einheitsgemeinde)\s+", "", n.strip())
    return re.sub(r",\s*(Stadt|Gemeinde)$", "", n).strip()


def prozent(stimmen: dict[str, int], gueltig: int, liste: list[str]) -> dict[str, float]:
    a = {p: round(stimmen.get(p, 0) / gueltig * 100, 1) for p in liste}
    a["Sonstige"] = round((gueltig - sum(stimmen.get(p, 0) for p in liste)) / gueltig * 100, 1)
    return a


def summe(gemeinden: dict[str, dict]) -> dict:
    s = {"wb": 0, "waehler": 0, "gueltig": 0, "stimmen": {}}
    for g in gemeinden.values():
        for k in ("wb", "waehler", "gueltig"):
            s[k] += g[k]
        for p, n in g["stimmen"].items():
            s["stimmen"][p] = s["stimmen"].get(p, 0) + n
    return s


def de(x: float, nach: int = 1) -> str:
    return f"{x:,.{nach}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def de_diff(x: float) -> str:
    return ("+" if x > 0 else "−" if x < 0 else "±") + de(abs(x))


def de_datum(iso: str) -> str:
    j, m, t = iso.split("-")
    return f"{int(t)}. {MONATE[int(m) - 1]} {j}"


def titel(w: dict) -> str:
    return f"{ART[w['art']]} {w['jahr']}"


def css_klasse(p: str) -> str:
    return "p-" + slug(p if p in FAMILIEN else "Sonstige")


def staerkste(a: dict[str, float]) -> tuple[str, float]:
    p = max((k for k in a if k != "Sonstige"), key=lambda k: a[k])
    return p, a[p]


def balken(a: dict[str, float], jahr: int, vor: dict[str, float] | None = None, vergleich: dict[str, float] | None = None,
           vergleich_name: str = "") -> str:
    zeilen = []
    for p, v in sorted(a.items(), key=lambda kv: (kv[0] == "Sonstige", -kv[1])):
        if v == 0 and p != "Sonstige":
            continue
        diff = ""
        if vor is not None:
            diff = f'<span class="wa-diff">{de_diff(round(v - vor[p], 1)) if p in vor and (vor[p] or p == "Sonstige") else "neu"}</span>'
        ref = ""
        if vergleich is not None and p in vergleich:
            ref = (f'<span class="wa-ref" style="left:{min(vergleich[p], 100):.1f}%" '
                   f'title="{e(vergleich_name)}: {de(vergleich[p])} %"></span>')
        zeilen.append(f'<div class="wa-zeile"><span class="wa-partei">{e(anzeige(p, jahr))}</span>'
                      f'<span class="wa-spur"><span class="wa-balken {css_klasse(p)}" style="width:{min(v, 100):.1f}%"></span>{ref}</span>'
                      f'<span class="wa-wert">{de(v)} %</span>{diff}</div>')
    return f'<div class="wa-balken-liste">{"".join(zeilen)}</div>'


# ---------------------------------------------------------------- Seiten

QUELLE = ('Daten: <a href="https://wahlergebnisse.sachsen-anhalt.de/">© Statistisches Landesamt Sachsen-Anhalt, Halle (Saale)</a>, '
          'endgültige Wahlergebnisse, auf die heutigen Gemeinden umgerechnet und ausgewertet. Ohne Gewähr. '
          'Das OK Lab Börde ist parteipolitisch neutral.')

NEUTRAL = ('<p class="wa-neutral">Das OK Lab Börde ist ehrenamtlich und parteipolitisch neutral. Diese Seiten zeigen die amtlichen '
           'Ergebnisse, ohne sie zu bewerten. Parteifarben dienen nur der Wiedererkennung.</p>')


def vorgaenger(wahlen: list[dict], i: int) -> dict | None:
    return next((w for w in reversed(wahlen[:i]) if w["art"] == wahlen[i]["art"]), None)


def uebersicht(daten: dict) -> str:
    wahlen = daten["wahlen"]
    w0 = wahlen[-1]
    kreis = daten["kreis"]
    k0 = kreis[w0["id"]]
    p0, v0 = staerkste(k0["anteile"])
    vw = vorgaenger(wahlen, len(wahlen) - 1)
    vor = kreis[vw["id"]]["anteile"] if vw else None
    gem = sorted(daten["gemeinden"].values(), key=lambda g: g["name"])
    zaehl: dict[str, int] = {}
    for g in gem:
        p, _ = staerkste(g["wahlen"][w0["id"]]["anteile"])
        zaehl[p] = zaehl.get(p, 0) + 1
    if len(zaehl) == 1:
        vorn_satz = f"Sie lag in allen {len(gem)} Gemeinden vorn."
    else:
        vorn_satz = "Vorn lag " + ", ".join(f"die {p} in {n} {'Gemeinde' if n == 1 else 'Gemeinden'}"
                                         for p, n in sorted(zaehl.items(), key=lambda kv: -kv[1])) + "."
    hoch = max(gem, key=lambda g: g["wahlen"][w0["id"]]["beteiligung"])
    tief = min(gem, key=lambda g: g["wahlen"][w0["id"]]["beteiligung"])

    # Stärkste Partei im Kreis je Wahl, für den Text
    erste = wahlen[0]
    k_erst = kreis[erste["id"]]
    pe, ve = staerkste(k_erst["anteile"])

    optionen = "".join(f'<option value="{e(p)}">Anteil {e(p)}</option>' for p in FAMILIEN[:9])
    marken = "".join(f'<option value="{i}" label="{w["jahr"]}"></option>' for i, w in enumerate(wahlen))
    art_knoepfe = "".join(
        f'<button type="button" data-art="{a}" aria-pressed="{"true" if a == "alle" else "false"}">{t}</button>'
        for a, t in (("alle", "Alle Wahlen"), ("LT", "Landtag"), ("BT", "Bundestag"), ("EW", "Europa")))

    liste_kopf = [p for p in daten["spalten"][w0["id"]]]
    kopf = "".join(f'<th scope="col">{e(anzeige(p, w0["jahr"]))}</th>' for p in liste_kopf)
    zeilen = []
    for g in gem:
        x = g["wahlen"][w0["id"]]
        zellen = "".join(f'<td>{de(x["anteile"].get(p, 0))}</td>' for p in liste_kopf)
        zeilen.append(f'<tr><th scope="row"><a href="/wahlen/{g["slug"]}/">{e(g["name"])}</a></th><td>{de(x["beteiligung"])}</td>{zellen}</tr>')
    zeilen.append(f'<tr class="wa-summe"><th scope="row">Landkreis Börde</th><td>{de(k0["beteiligung"])}</td>'
                  + "".join(f'<td>{de(k0["anteile"].get(p, 0))}</td>' for p in liste_kopf) + "</tr>")

    verlauf = "".join(
        f'<tr><th scope="row">{e(titel(w))}</th><td>{de_datum(w["datum"])}</td>'
        f'<td>{de(kreis[w["id"]]["beteiligung"])} %{"" if kreis[w["id"]]["briefwahl"] else "¹"}</td>'
        f'<td>{e(anzeige(*[staerkste(kreis[w["id"]]["anteile"])[0]], w["jahr"]))} ({de(staerkste(kreis[w["id"]]["anteile"])[1])} %)</td></tr>'
        for w in reversed(wahlen))

    gemeinde_links = "".join(f'<li><a href="/wahlen/{g["slug"]}/">{e(g["name"])}</a></li>' for g in gem)

    return f"""<header class="wa-kopf">
  <h1>Wahlatlas Börde: Wahlergebnisse seit 1990</h1>
  <p class="lead">Wie haben die 34 Gemeinden im Landkreis Börde gewählt? Alle {len(wahlen)} Landtags-, Bundestags- und Europawahlen von 1990 bis {w0['jahr']} auf einer Karte, umgerechnet auf die heutigen Gemeinden. Mit Zeitreise, Wahlbeteiligung und einer eigenen Seite für jede Gemeinde.</p>
</header>

<section aria-labelledby="wa-kreis">
  <h2 id="wa-kreis">{e(titel(w0))} im Landkreis Börde</h2>
  <p>Bei der {e(titel(w0))} am {de_datum(w0['datum'])} gingen im Landkreis Börde <strong>{de(k0['beteiligung'])} %</strong> der Wahlberechtigten wählen{f" ({de_diff(round(k0['beteiligung'] - kreis[vw['id']]['beteiligung'], 1))} Prozentpunkte gegenüber {vw['jahr']})" if vw else ""}. Stärkste Partei bei den {STIMME[w0['art']]} wurde die {e(p0)} mit {de(v0)} %. {e(vorn_satz)} Die höchste Wahlbeteiligung hatte {e(hoch['name'])} mit {de(hoch['wahlen'][w0['id']]['beteiligung'])} %, die niedrigste {e(tief['name'])} mit {de(tief['wahlen'][w0['id']]['beteiligung'])} %.</p>
  <figure class="wa-figur">
    {balken(k0['anteile'], w0['jahr'], vor)}
    <figcaption>{STIMME[w0['art']]} im Landkreis Börde in Prozent, daneben die Veränderung gegenüber der {e(titel(vw)) if vw else ''} in Prozentpunkten.</figcaption>
  </figure>
</section>

<section aria-labelledby="wa-zeitreise">
  <h2 id="wa-zeitreise">Zeitreise: 36 Jahre Wahlen in der Börde</h2>
  <p>Wählen Sie eine Wahl auf der Zeitleiste oder spielen Sie alle nacheinander ab. Die Karte zeigt, welche Partei in welcher Gemeinde vorn lag, wie hoch die Wahlbeteiligung war oder wie stark eine bestimmte Partei abgeschnitten hat.</p>
  <div class="wa-filter">
    <div role="group" aria-label="Wahlart">{art_knoepfe}</div>
    <label>Ansicht <select id="wa-ansicht"><option value="staerkste">Stärkste Partei</option><option value="beteiligung">Wahlbeteiligung</option>{optionen}</select></label>
  </div>
  <div class="wa-zeitleiste">
    <button type="button" id="wa-play" aria-label="Alle Wahlen nacheinander abspielen">▶</button>
    <input type="range" id="wa-zeit" min="0" max="{len(wahlen) - 1}" value="{len(wahlen) - 1}" step="1" list="wa-marken" aria-label="Wahl auswählen">
    <datalist id="wa-marken">{marken}</datalist>
    <output id="wa-zeit-text" for="wa-zeit">{e(titel(w0))}</output>
  </div>
  <p id="wa-hinweis" class="wa-hinweis" hidden></p>
  <div class="wa-zeitreise">
    <figure class="wa-figur wa-figur-karte">
      <div id="wa-legende" class="wa-legende"></div>
      <div id="wa-map" class="wa-map"></div>
      <figcaption>Ein Klick auf eine Gemeinde öffnet ihre Seite mit allen Ergebnissen seit 1990.</figcaption>
    </figure>
    <figure class="wa-figur">
      <div id="wa-kreis-balken">{balken(k0['anteile'], w0['jahr'])}</div>
      <figcaption id="wa-kreis-text">{STIMME[w0['art']]} im Landkreis Börde, Wahlbeteiligung {de(k0['beteiligung'])} %.</figcaption>
    </figure>
  </div>
</section>

<section aria-labelledby="wa-trend">
  <h2 id="wa-trend">Die Parteien im Landkreis seit 1990</h2>
  <p>Zu Beginn lag die {e(pe)} mit {de(ve)} % vorn ({e(titel(erste))}). Die Linien zeigen die Ergebnisse der größeren Parteien im Landkreis bei allen Wahlen, die Wahlart ist an der Form der Punkte zu erkennen.</p>
  <figure class="wa-figur">
    <div id="wa-trend-chart" class="wa-chart"></div>
    <figcaption>{STIMME['LT']} bzw. Stimmen im Landkreis Börde in Prozent. Bis 2006 sind die Werte die Summe der heutigen Gemeinden ohne Briefwahl, ab 2009 die amtlichen Kreisergebnisse.</figcaption>
  </figure>
</section>

<section aria-labelledby="wa-tabelle">
  <h2 id="wa-tabelle">Alle Gemeinden: {e(titel(w0))}</h2>
  <div class="wa-tabelle-wrap">
  <table class="wa-tabelle">
    <caption>Wahlbeteiligung und {STIMME[w0['art']]} je Gemeinde in Prozent</caption>
    <thead><tr><th scope="col">Gemeinde</th><th scope="col">Beteiligung</th>{kopf}</tr></thead>
    <tbody>{''.join(zeilen)}</tbody>
  </table>
  </div>
</section>

<section aria-labelledby="wa-verlauf">
  <h2 id="wa-verlauf">Alle Wahlen seit 1990</h2>
  <div class="wa-tabelle-wrap">
  <table class="wa-tabelle wa-schmal">
    <thead><tr><th scope="col">Wahl</th><th scope="col">Datum</th><th scope="col">Beteiligung</th><th scope="col">Stärkste Partei</th></tr></thead>
    <tbody>{verlauf}</tbody>
  </table>
  </div>
  <p class="wa-klein">¹ Ohne Briefwahl. Bis 2006 gab es den Landkreis Börde in seinen heutigen Grenzen noch nicht; die Werte sind die Summe der heutigen Gemeinden, und dort wurde die Briefwahl nicht erfasst.</p>
</section>

<section aria-labelledby="wa-gemeinden">
  <h2 id="wa-gemeinden">Ergebnisse nach Gemeinde</h2>
  <p>Jede Gemeinde hat eine eigene Seite mit allen Wahlen seit 1990, dem Vergleich zum Landkreis und der Entwicklung der Wahlbeteiligung.</p>
  <ul class="wa-gemeindeliste">{gemeinde_links}</ul>
</section>

<section class="wa-text" aria-labelledby="wa-lesen">
  <h2 id="wa-lesen">So sind die Zahlen zu lesen</h2>
  <h3>Umgerechnet auf die heutigen Gemeinden</h3>
  <p>1990 bestand das Gebiet des heutigen Landkreises aus rund 160 Gemeinden in vier Kreisen. Seitdem wurden Kreise und Gemeinden mehrfach zusammengelegt, zuletzt 2007 zum Landkreis Börde und 2009/2010 zu den heutigen 34 Gemeinden. Das Statistische Landesamt ordnet jeder früheren Gemeinde ihre heutige Nachfolgegemeinde zu. Der Atlas zählt die Stimmen aller Vorgängergemeinden zusammen. So lassen sich auch die Wahlen der 1990er Jahre mit heute vergleichen.</p>
  <h3>Briefwahl erst ab 2021 in den Gemeindeergebnissen</h3>
  <p>Bis 2019 wurde die Briefwahl in kreisangehörigen Gemeinden nicht nach Gemeinden ausgezählt, sondern nur für den ganzen Kreis. Die Gemeindewerte dieser Jahre enthalten daher nur die Stimmen aus den Wahllokalen. Die Wahlbeteiligung ist dort entsprechend niedriger angegeben, und weil Briefwählende etwas anders wählen, können auch die Parteianteile leicht abweichen. Ab 2009 nennt der Atlas für den Landkreis die amtlichen Ergebnisse mit Briefwahl.</p>
  <h3>Zweitstimme und Erststimme</h3>
  <p>Bei Landtags- und Bundestagswahlen hat jede Wählerin und jeder Wähler zwei Stimmen. Mit der Erststimme wird eine Person im Wahlkreis gewählt, mit der Zweitstimme eine Partei. Die Zweitstimmen entscheiden über die Sitzverteilung, darum zeigt der Atlas sie. Bei der Europawahl gibt es nur eine Stimme.</p>
  <h3>Parteien über die Zeit</h3>
  <p>Manche Parteien haben ihren Namen geändert. Die PDS hieß ab 2005 Linkspartei.PDS und ab 2007 Die Linke; der Atlas führt sie als eine Linie. Kleinere Parteien, die im Landkreis unter {de(SCHWELLE, 0)} % blieben, sind unter „Sonstige“ zusammengefasst.</p>
  <h3>Kleine Gemeinden</h3>
  <p>In Gemeinden mit wenigen hundert Wahlberechtigten verändern schon einzelne Stimmen das Ergebnis um mehrere Prozentpunkte. Große Ausschläge sind dort mit Vorsicht zu lesen.</p>
</section>

<section class="wa-text" aria-labelledby="wa-faq">
  <h2 id="wa-faq">Häufige Fragen</h2>
  <div class="wa-faq">{{faq}}</div>
</section>

<section class="wa-text" aria-labelledby="wa-daten">
  <h2 id="wa-daten">Über die Daten</h2>
  <p>Alle Zahlen sind die endgültigen amtlichen Ergebnisse, die das Statistische Landesamt Sachsen-Anhalt im Auftrag der Landeswahlleitung veröffentlicht. Der Atlas übernimmt sie unverändert, zählt Vorgängergemeinden zusammen und fasst kleinere Parteien unter „Sonstige“ zusammen. Alle Zahlen gibt es als <a href="/wahlen/data.json">JSON-Datei</a>.</p>
  {NEUTRAL}
</section>"""


def faq_liste(daten: dict) -> list[tuple[str, str]]:
    wahlen = daten["wahlen"]
    kreis = daten["kreis"]
    w0 = wahlen[-1]
    bt = next(w for w in reversed(wahlen) if w["art"] == "BT")
    k0, kb = kreis[w0["id"]], kreis[bt["id"]]
    p0, v0 = staerkste(k0["anteile"])
    pb, vb = staerkste(kb["anteile"])
    hoch = max(wahlen, key=lambda w: kreis[w["id"]]["beteiligung"] if kreis[w["id"]]["briefwahl"] else 0)
    folgende = ", ".join(f"{p} ({de(v)} %)" for p, v in sorted(k0["anteile"].items(), key=lambda kv: -kv[1])
                         if p not in ("Sonstige", p0) and v >= 1)
    return [
        (f"Wie hat der Landkreis Börde bei der {titel(w0)} gewählt?",
         f"Bei der {titel(w0)} am {de_datum(w0['datum'])} wurde die {p0} mit {de(v0)} % der Zweitstimmen stärkste Partei "
         f"im Landkreis Börde. Es folgten {folgende}."),
        ("Wie hoch war die Wahlbeteiligung in der Börde?",
         f"Bei der {titel(w0)} lag sie im Landkreis Börde bei {de(k0['beteiligung'])} %. Die höchste Beteiligung seit 2009 "
         f"hatte die {titel(hoch)} mit {de(kreis[hoch['id']]['beteiligung'])} %."),
        (f"Wie hat die Börde bei der {titel(bt)} gewählt?",
         f"Stärkste Partei bei den Zweitstimmen wurde im Landkreis Börde die {pb} mit {de(vb)} %."),
        ("Kann man Wahlergebnisse von 1990 mit heute vergleichen?",
         "Ja, der Atlas rechnet alle Wahlen auf die heutigen 34 Gemeinden um. Bis 2019 fehlen in den Gemeindewerten aber die "
         "Briefwahlstimmen, weil sie nur für den ganzen Kreis ausgezählt wurden."),
        ("Woher stammen die Zahlen?",
         "Es sind die endgültigen amtlichen Ergebnisse, veröffentlicht vom Statistischen Landesamt Sachsen-Anhalt auf "
         "wahlergebnisse.sachsen-anhalt.de."),
        ("Wann sind die nächsten Wahlen?",
         "Regulär finden 2029 die nächsten Kommunal-, Europa- und Bundestagswahlen statt, die nächste Landtagswahl 2031. "
         "Bürgermeisterwahlen haben in jeder Gemeinde eigene Termine."),
    ]


def faq_html(faq: list[tuple[str, str]]) -> str:
    return "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)


def gemeinde_seite(g: dict, daten: dict) -> str:
    wahlen = daten["wahlen"]
    kreis = daten["kreis"]
    w0 = wahlen[-1]
    x0 = g["wahlen"][w0["id"]]
    p0, v0 = staerkste(x0["anteile"])
    neu = [w for w in wahlen if w["briefwahl"]][::-1]
    teile = []
    for w in neu:
        i = wahlen.index(w)
        x = g["wahlen"][w["id"]]
        vw = vorgaenger(wahlen, i)
        vor = g["wahlen"][vw["id"]]["anteile"] if vw and vw["briefwahl"] else None
        teile.append(f"""<section aria-labelledby="w-{w['id']}">
  <h2 id="w-{w['id']}">{e(titel(w))}</h2>
  <p class="wa-meta">{de_datum(w['datum'])} · Wahlbeteiligung {de(x['beteiligung'])} % (Landkreis {de(kreis[w['id']]['beteiligung'])} %) · {de(x['wb'], 0)} Wahlberechtigte</p>
  {balken(x['anteile'], w['jahr'], vor, kreis[w['id']]['anteile'], 'Landkreis Börde')}
  <p class="wa-klein">{STIMME[w['art']]} in Prozent.{(' Daneben die Veränderung gegenüber ' + titel(vw) + ' in Prozentpunkten.') if vor else ''} Der senkrechte Strich zeigt den Wert im Landkreis.</p>
</section>""")

    # Tabelle aller Wahlen: Familien, die in der Gemeinde je über 3 % kamen
    fam = [p for p in FAMILIEN if any(g["wahlen"][w["id"]]["anteile"].get(p, 0) >= SCHWELLE for w in wahlen)]
    kopf = "".join(f'<th scope="col">{e(p)}</th>' for p in fam)
    zeilen = "".join(
        f'<tr><th scope="row">{e(titel(w))}{"" if w["briefwahl"] else "¹"}</th><td>{de(g["wahlen"][w["id"]]["beteiligung"])}</td>'
        + "".join(f'<td>{de(g["wahlen"][w["id"]]["anteile"][p]) if p in g["wahlen"][w["id"]]["anteile"] and (g["wahlen"][w["id"]]["anteile"][p] or p in daten["spalten"][w["id"]]) else "–"}</td>' for p in fam)
        + "</tr>" for w in reversed(wahlen))
    ort = f'<li><a href="/orte/{g["slug"]}/">Ortssteckbrief {e(g["name"])}</a></li>' if (ROOT / "orte" / g["slug"]).exists() else ""
    erste = wahlen[0]
    pe, ve = staerkste(g["wahlen"][erste["id"]]["anteile"])
    return f"""<header class="wa-kopf">
  <h1>Wahlergebnisse {e(g['name'])}</h1>
  <p class="lead">So hat die Gemeinde {e(g['name'])} im Landkreis Börde gewählt: alle {len(wahlen)} Landtags-, Bundestags- und Europawahlen seit 1990, umgerechnet auf das heutige Gemeindegebiet, mit Wahlbeteiligung und Vergleich zum Landkreis.</p>
</header>
<p>Bei der {e(titel(w0))} am {de_datum(w0['datum'])} lag die Wahlbeteiligung in {e(g['name'])} bei <strong>{de(x0['beteiligung'])} %</strong>. Stärkste Partei bei den Zweitstimmen wurde die {e(p0)} mit {de(v0)} %. Bei der ersten Wahl nach der Wiedervereinigung, der {e(titel(erste))}, lag im heutigen Gemeindegebiet die {e(anzeige(pe, erste['jahr']))} mit {de(ve)} % vorn.</p>
{''.join(teile)}
<section aria-labelledby="w-alle">
  <h2 id="w-alle">Alle Wahlen seit 1990</h2>
  <figure class="wa-figur"><div id="wa-gem-chart" class="wa-chart" data-ags="{g['ags']}"></div>
  <figcaption>Ergebnisse der größeren Parteien in {e(g['name'])} bei allen Wahlen seit 1990, in Prozent.</figcaption></figure>
  <div class="wa-tabelle-wrap"><table class="wa-tabelle">
    <caption>Wahlbeteiligung und Stimmenanteile in Prozent</caption>
    <thead><tr><th scope="col">Wahl</th><th scope="col">Beteiligung</th>{kopf}</tr></thead>
    <tbody>{zeilen}</tbody>
  </table></div>
  <p class="wa-klein">¹ Nur Stimmen aus den Wahllokalen, ohne Briefwahl. Bis 2019 wurde die Briefwahl nicht nach Gemeinden ausgezählt. Bis 2009 sind die Werte die Summe der Vorgängergemeinden. Parteien unter {de(SCHWELLE, 0)} % im Landkreis zählen zu „Sonstige“ und sind hier nicht aufgeführt.</p>
</section>
<section aria-labelledby="w-mehr">
  <h2 id="w-mehr">Mehr zur Gemeinde</h2>
  <ul class="wa-links"><li><a href="/wahlen/">Wahlatlas Börde: alle Gemeinden auf einer Karte, mit Zeitreise</a></li>{ort}<li><a href="https://wahlergebnisse.sachsen-anhalt.de/">Wahlportal des Landes mit Ergebnissen bis auf Wahlbezirke</a></li></ul>
  {NEUTRAL}
</section>"""


def main() -> None:
    if "--legenden" in sys.argv:
        legenden_einlesen()
        return
    legenden = json.loads(LEGENDEN.read_text("utf-8"))
    roh, roh_kreis = {}, {}
    for wid, art, datum, gem, krs, dsb, _ in W:
        roh[wid] = lesen(wid, art, gem, legenden.get(wid))
        if len(roh[wid]) != 34:
            raise SystemExit(f"{wid}: {len(roh[wid])} Gemeinden statt 34")
        if krs:
            roh_kreis[wid] = lesen(wid, art, krs, legenden.get(wid), nur_kreis=True)[KREIS]
    letzte = W[-1][0]
    namen = {ags: gemeinde_name(g["name"]) for ags, g in roh[letzte].items()}
    if any(set(r) != set(namen) for r in roh.values()):
        raise SystemExit("Gemeindeschlüssel passen nicht zusammen")

    wahlen, spalten, kreis = [], {}, {}
    for wid, art, datum, gem, krs, dsb, brief in W:
        jahr = int(datum[:4])
        wahlen.append({"id": wid, "art": art, "datum": datum, "jahr": jahr, "briefwahl": brief,
                       "titel": f"{ART[art]} {jahr}", "kurz": f"{ART_KURZ[art]} {jahr}", "stimme": STIMME[art]})
        k = roh_kreis.get(wid) or summe(roh[wid])
        anteil_k = {p: n / k["gueltig"] * 100 for p, n in k["stimmen"].items()}
        liste = [p for p in FAMILIEN if p in k["stimmen"] and (p in IMMER or anteil_k[p] >= SCHWELLE)]
        liste += sorted((p for p in k["stimmen"] if p not in FAMILIEN and anteil_k[p] >= SCHWELLE), key=lambda p: -anteil_k[p])
        spalten[wid] = liste
        kreis[wid] = {"wb": k["wb"], "waehler": k["waehler"], "gueltig": k["gueltig"],
                      "beteiligung": round(k["waehler"] / k["wb"] * 100, 1),
                      "briefwahl": brief or wid in roh_kreis, "anteile": prozent(k["stimmen"], k["gueltig"], liste)}

    gemeinden = {}
    for ags, name in sorted(namen.items(), key=lambda kv: kv[1]):
        eintrag = {"ags": ags, "name": name, "slug": slug(name), "wahlen": {}}
        for w in wahlen:
            g = roh[w["id"]][ags]
            eintrag["wahlen"][w["id"]] = {"wb": g["wb"], "waehler": g["waehler"], "gueltig": g["gueltig"],
                                          "beteiligung": round(g["waehler"] / g["wb"] * 100, 1),
                                          "anteile": prozent(g["stimmen"], g["gueltig"], spalten[w["id"]])}
        gemeinden[ags] = eintrag
    daten = {"quelle": "© Statistisches Landesamt Sachsen-Anhalt, Halle (Saale), wahlergebnisse.sachsen-anhalt.de",
             "hinweis": "Bis 2019 enthalten die Gemeindewerte keine Briefwahl. Vorgängergemeinden sind zusammengezählt.",
             "wahlen": wahlen, "spalten": spalten, "familien": FAMILIEN, "kreis": kreis, "gemeinden": gemeinden}

    geo = json.loads((ROOT / "zeitschichten" / "gemeinden.geojson").read_text("utf-8"))
    fehlend = set(namen.values()) - {f["properties"]["name"] for f in geo["features"]}
    if fehlend:
        raise SystemExit(f"Gemeinden ohne Grenze: {fehlend}")

    OUT.mkdir(exist_ok=True)
    (OUT / "data.json").write_text(json.dumps(daten, ensure_ascii=False, separators=(",", ":")), "utf-8", newline="\n")

    faq = faq_liste(daten)
    w0 = wahlen[-1]
    jsonld = [
        {"@context": "https://schema.org", "@type": "Dataset", "name": "Wahlergebnisse der Gemeinden im Landkreis Börde seit 1990",
         "description": f"Amtliche Endergebnisse aller {len(wahlen)} Landtags-, Bundestags- und Europawahlen seit 1990 für die "
                        "34 Gemeinden im Landkreis Börde, umgerechnet auf den heutigen Gebietsstand: Wahlbeteiligung und Stimmenanteile.",
         "url": f"{BASIS_URL}/wahlen/", "inLanguage": "de", "isAccessibleForFree": True,
         "temporalCoverage": f"{wahlen[0]['datum']}/{w0['datum']}",
         "spatialCoverage": {"@type": "Place", "name": "Landkreis Börde, Sachsen-Anhalt"},
         "creator": {"@type": "Organization", "name": "OK Lab Börde", "url": f"{BASIS_URL}/"},
         "isBasedOn": "https://wahlergebnisse.sachsen-anhalt.de/",
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                           "contentUrl": f"{BASIS_URL}/wahlen/data.json"}]},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    kopf = '<link rel="stylesheet" href="/assets/wahlen.css">\n  <script defer src="/assets/wahlen.js"></script>'
    html = seite(titel="Wahlatlas Börde: Wahlergebnisse aller Gemeinden seit 1990 | OK Lab Börde",
                 beschreibung=(f"Wie haben die Gemeinden im Landkreis Börde gewählt? Alle Wahlen von 1990 bis {w0['jahr']} "
                               "auf einer Karte, mit Zeitreise, Wahlbeteiligung und Seite je Gemeinde."),
                 pfad="/wahlen/", inhalt=uebersicht(daten).replace("{faq}", faq_html(faq)),
                 brotkrumen=[("Start", "/"), ("Wahlatlas", None)], jsonld=jsonld, extra_head=kopf, quelle=QUELLE)
    (OUT / "index.html").write_text(html, "utf-8", newline="\n")

    for g in gemeinden.values():
        x0 = g["wahlen"][w0["id"]]
        p0, v0 = staerkste(x0["anteile"])
        ld = {"@context": "https://schema.org", "@type": "Dataset", "name": f"Wahlergebnisse {g['name']} seit 1990",
              "description": f"Amtliche Endergebnisse aller Landtags-, Bundestags- und Europawahlen seit 1990 für die Gemeinde "
                             f"{g['name']} im Landkreis Börde.",
              "url": f"{BASIS_URL}/wahlen/{g['slug']}/", "inLanguage": "de", "isAccessibleForFree": True,
              "temporalCoverage": f"{wahlen[0]['datum']}/{w0['datum']}",
              "spatialCoverage": {"@type": "Place", "name": f"{g['name']}, Landkreis Börde"},
              "creator": {"@type": "Organization", "name": "OK Lab Börde", "url": f"{BASIS_URL}/"},
              "isBasedOn": "https://wahlergebnisse.sachsen-anhalt.de/"}
        html = seite(titel=f"Wahlergebnisse {g['name']} seit 1990: {titel(w0)} | OK Lab Börde",
                     beschreibung=(f"So hat {g['name']} gewählt: {titel(w0)} mit {de(x0['beteiligung'])} % Wahlbeteiligung, "
                                   f"stärkste Partei {p0} ({de(v0)} %). Alle Wahlen seit 1990 im Vergleich zum Landkreis Börde."),
                     pfad=f"/wahlen/{g['slug']}/", inhalt=gemeinde_seite(g, daten),
                     brotkrumen=[("Start", "/"), ("Wahlatlas", "/wahlen/"), (g["name"], None)], jsonld=ld,
                     extra_head=kopf, quelle=QUELLE)
        (OUT / g["slug"]).mkdir(exist_ok=True)
        (OUT / g["slug"] / "index.html").write_text(html, "utf-8", newline="\n")

    for w in wahlen:
        k = kreis[w["id"]]
        print(f"{w['titel']:22} Bet. {k['beteiligung']:5.1f}{'' if k['briefwahl'] else '*'}  "
              + ", ".join(f"{anzeige(p, w['jahr'])} {v}" for p, v in sorted(k["anteile"].items(), key=lambda kv: -kv[1])[:6]))


if __name__ == "__main__":
    main()
