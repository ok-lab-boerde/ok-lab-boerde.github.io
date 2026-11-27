"""Dürremonitor Börde: Bodenfeuchte des DWD für Stationen in und am Landkreis Börde.

Lädt die berechneten Tageswerte zur Bodenfeuchte (Modell AMBAV) und die Klima-Tageswerte (Niederschlag)
vom Open-Data-Server des Deutschen Wetterdienstes und erzeugt `duerre/index.html` und `duerre/data.json`.
Nur Standardbibliothek. Aufruf: python scripts/duerre/build.py
"""
from __future__ import annotations

import datetime as dt
import gzip
import io
import json
import statistics
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "orte"))
from seiten import BASIS_URL, e, seite  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
OUT = ROOT / "duerre"
DWD = "https://opendata.dwd.de/climate_environment/CDC"
BODEN = f"{DWD}/derived_germany/soil/daily"
KLIMA = f"{DWD}/observations_germany/climate/daily/kl"
NORMAL = (1991, 2020)

# Stationen: id, Name, Lage (für den Text), Breite, Länge
STATIONEN = [
    (5158, "Ummendorf", "im Westen des Landkreises, mitten im Lössgebiet der Börde", 52.16, 11.18),
    (3126, "Magdeburg", "am Ostrand des Landkreises, an der Elbe", 52.10, 11.58),
    (1544, "Gardelegen", "nördlich des Landkreises, Richtung Altmark und Letzlinger Heide", 52.51, 11.39),
    (6266, "Huy-Pabstorf", "südwestlich des Landkreises, im nördlichen Harzvorland", 52.03, 10.96),
]

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]


# ---------------------------------------------------------------- Laden

def holen(url: str, ziel: Path, max_alter_h: float) -> bytes:
    """Datei laden und zwischenspeichern; `max_alter_h` steuert, wie lange der Zwischenspeicher gilt."""
    if ziel.exists() and (dt.datetime.now().timestamp() - ziel.stat().st_mtime) < max_alter_h * 3600:
        return ziel.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "ok-lab-boerde-duerremonitor"})
    with urllib.request.urlopen(req, timeout=120) as r:
        daten = r.read()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(daten)
    return daten


def verzeichnis(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ok-lab-boerde-duerremonitor"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def tabelle(text: str) -> list[dict]:
    zeilen = [z for z in text.splitlines() if z.strip()]
    kopf = [k.strip() for k in zeilen[0].split(";")]
    return [dict(zip(kopf, (w.strip() for w in z.split(";")))) for z in zeilen[1:]]


def zahl(w: str | None) -> float | None:
    try:
        x = float(w)
    except (TypeError, ValueError):
        return None
    return None if x <= -999 else x


def datum(s: str) -> dt.date:
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def boden(sid: int) -> dict[dt.date, dict]:
    werte: dict[dt.date, dict] = {}
    for teil, alter in (("historical", 24 * 7), ("recent", 6)):
        name = f"derived_germany_soil_daily_{teil}_v2_{sid}.txt.gz"
        roh = gzip.decompress(holen(f"{BODEN}/{teil}/{name}", CACHE / name, alter)).decode("latin-1")
        for z in tabelle(roh):
            werte[datum(z["Datum"])] = z
    return werte


def niederschlag(sid: int) -> dict[dt.date, float]:
    werte: dict[dt.date, float] = {}
    sid5 = f"{sid:05d}"
    liste = verzeichnis(f"{KLIMA}/historical/")
    hist = sorted({t.split('"')[0] for t in liste.split('href="')[1:] if t.startswith(f"tageswerte_KL_{sid5}_")})
    for teil, name, alter in [("historical", n, 24 * 7) for n in hist] + [("recent", f"tageswerte_KL_{sid5}_akt.zip", 6)]:
        z = zipfile.ZipFile(io.BytesIO(holen(f"{KLIMA}/{teil}/{name}", CACHE / name, alter)))
        produkt = next(n for n in z.namelist() if n.startswith("produkt_"))
        for zeile in tabelle(z.read(produkt).decode("latin-1")):
            r = zahl(zeile.get("RSK"))
            if r is not None:
                werte[datum(zeile["MESS_DATUM"])] = r
    return werte


# ---------------------------------------------------------------- Rechnen

def tag_index(d: dt.date) -> int:
    """Tag im Jahr 0..364; der 29. Februar zählt wie der 28."""
    i = (d - dt.date(d.year, 1, 1)).days
    schalt = d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)
    return i - 1 if schalt and i >= 59 else i


def quantil(werte: list[float], q: float) -> float:
    w = sorted(werte)
    k = (len(w) - 1) * q
    u = int(k)
    return w[u] + (w[min(u + 1, len(w) - 1)] - w[u]) * (k - u)


def rund(x: float | None) -> float | None:
    return None if x is None else round(x, 1)


def zustand(nfk: float) -> tuple[str, str]:
    if nfk < 30:
        return "Trockenstress", "kritisch"
    if nfk < 50:
        return "knapp", "warnung"
    if nfk <= 80:
        return "gut versorgt", "gut"
    if nfk <= 100:
        return "feucht", "feucht"
    return "sehr nass", "feucht"


def duerre_klasse(perzentil: float) -> str:
    """Einteilung angelehnt an den Dürremonitor des UFZ (Perzentile der Bodenfeuchte)."""
    if perzentil < 2:
        return "außergewöhnliche Dürre"
    if perzentil < 5:
        return "extreme Dürre"
    if perzentil < 10:
        return "schwere Dürre"
    if perzentil < 20:
        return "moderate Dürre"
    if perzentil < 30:
        return "ungewöhnlich trocken"
    return "keine Dürre"


def auswerten(sid: int) -> dict:
    bd = boden(sid)
    rr = niederschlag(sid)
    tage = sorted(d for d, z in bd.items() if zahl(z.get("BFGL_AG")) is not None)
    heute = tage[-1]
    z0 = bd[heute]

    def wert(d: dt.date, k: str) -> float | None:
        z = bd.get(d)
        return zahl(z.get(k)) if z else None

    # Vergleichszeitraum je Kalendertag, geglättet über ±3 Tage
    je_tag: list[list[float]] = [[] for _ in range(365)]
    je_tag_genau: list[dict[int, float]] = [{} for _ in range(365)]
    for d in tage:
        if NORMAL[0] <= d.year <= NORMAL[1]:
            v = wert(d, "BFGL_AG")
            i = tag_index(d)
            je_tag_genau[i][d.year] = v
            for k in range(-3, 4):
                je_tag[(i + k) % 365].append(v)
    band = [[round(quantil(w, .1)), round(quantil(w, .5)), round(quantil(w, .9))] for w in je_tag]

    loess = wert(heute, "BFGL_AG")
    vergleich = list(je_tag_genau[tag_index(heute)].values())
    trockener = sum(1 for v in vergleich if v > loess)  # so viele Jahre waren feuchter als heute
    perzentil = (sum(1 for v in vergleich if v < loess) + .5 * sum(1 for v in vergleich if v == loess)) / len(vergleich) * 100

    # letzte 365 Tage für die Grafik
    start = heute - dt.timedelta(days=364)
    reihe_l, reihe_s = [], []
    for k in range(365):
        d = start + dt.timedelta(days=k)
        reihe_l.append(wert(d, "BFGL_AG"))
        reihe_s.append(wert(d, "BFGS_AG"))

    # Trockenstress-Tage je Jahr (Löss unter Gras unter 30 % nFK)
    jahre: dict[int, list[int]] = {}
    for d in tage:
        j = jahre.setdefault(d.year, [0, 0])
        j[1] += 1
        if wert(d, "BFGL_AG") < 30:
            j[0] += 1
    stress = [[j, n] for j, (n, gesamt) in sorted(jahre.items()) if gesamt >= 300 or j == heute.year]

    # Niederschlag
    def summe(von: dt.date, bis: dt.date) -> float | None:
        werte = [rr.get(von + dt.timedelta(days=k)) for k in range((bis - von).days + 1)]
        fehlend = sum(1 for w in werte if w is None)
        return None if fehlend > len(werte) * .1 else sum(w for w in werte if w is not None)

    def normal_summe(tag_von: dt.date, tag_bis: dt.date) -> float | None:
        s = []
        for j in range(NORMAL[0], NORMAL[1] + 1):
            try:
                a = tag_von.replace(year=j - (tag_bis.year - tag_von.year))
                b = tag_bis.replace(year=j)
            except ValueError:
                continue
            x = summe(a, b)
            if x is not None:
                s.append(x)
        return statistics.mean(s) if len(s) >= 25 else None

    von30 = heute - dt.timedelta(days=29)
    vonjahr = dt.date(heute.year, 1, 1)
    verdunstung30 = sum(wert(von30 + dt.timedelta(days=k), "VPGFAO") or 0 for k in range(30))
    jahressummen = [summe(dt.date(j, 1, 1), dt.date(j, 12, 31)) for j in range(NORMAL[0], NORMAL[1] + 1)]
    jahressummen = [x for x in jahressummen if x is not None]

    return {
        "id": sid,
        "stand": heute.isoformat(),
        "loess": loess,
        "sand": wert(heute, "BFGS_AG"),
        "weizen": wert(heute, "BFWL_AG"),
        "mais": wert(heute, "BFML_AG"),
        "schichten": [wert(heute, f"BFGL0{k}_AG") for k in range(1, 7)],
        "trockener_als": trockener,
        "vergleich_jahre": len(vergleich),
        "perzentil": round(perzentil),
        "median_heute": band[tag_index(heute)][1],
        "rr30": rund(summe(von30, heute)),
        "rr30_normal": rund(normal_summe(von30, heute)),
        "rrjahr": rund(summe(vonjahr, heute)),
        "rrjahr_normal": rund(normal_summe(vonjahr, heute)),
        "rr_jahresmittel": round(statistics.mean(jahressummen)) if len(jahressummen) >= 25 else None,
        "etp30": round(verdunstung30),
        "frost": zahl(z0.get("ZFUMI")),
        "start": start.isoformat(),
        "reihe_loess": reihe_l,
        "reihe_sand": reihe_s,
        "band": band,
        "stress": stress,
    }


# ---------------------------------------------------------------- Seite

def de_zahl(x: float | None, nach: int = 0) -> str:
    if x is None:
        return "–"
    return f"{x:,.{nach}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def de_datum(d: dt.date) -> str:
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def jahreszeit_text(d: dt.date) -> str:
    teil = "Anfang" if d.day <= 10 else "Mitte" if d.day <= 20 else "Ende"
    return f"{teil} {MONATE[d.month - 1]}"


def rr_vergleich(ist: float | None, normal: float | None) -> str:
    if ist is None or normal is None or normal == 0:
        return ""
    p = round(ist / normal * 100)
    return f"{p} % des Üblichen"


def stations_karte(s: dict, name: str, lage: str) -> str:
    text, klasse = zustand(s["loess"])
    stand = dt.date.fromisoformat(s["stand"])
    rr = rr_vergleich(s["rr30"], s["rr30_normal"])
    return f"""<article class="dm-station" id="station-{s['id']}">
  <h3>{e(name)}</h3>
  <p class="dm-lage">{e(lage)}</p>
  <p class="dm-wert"><span class="zahl">{de_zahl(s['loess'])} %</span> <span class="dm-status dm-{klasse}">{e(text)}</span></p>
  <p class="dm-klein">Bodenfeuchte in 0–60 cm, Lössboden unter Gras</p>
  <dl>
    <dt>Vergleich {'1991' if s['vergleich_jahre'] >= 30 else NORMAL[1] - s['vergleich_jahre'] + 1}–{NORMAL[1]}</dt><dd>{duerre_klasse(s['perzentil'])} · feuchter waren {s['trockener_als']} von {s['vergleich_jahre']} Jahren</dd>
    <dt>Sandboden</dt><dd>{de_zahl(s['sand'])} % nFK ({e(zustand(s['sand'])[0])})</dd>
    <dt>Regen 30 Tage</dt><dd>{de_zahl(s['rr30'])} mm{(' · ' + rr) if rr else ''}</dd>
  </dl>
  <p class="dm-klein">Stand: {de_datum(stand)}</p>
</article>"""


def erzeugen(werte: list[dict]) -> None:
    namen = {sid: (name, lage, lat, lon) for sid, name, lage, lat, lon in STATIONEN}
    haupt = werte[0]
    stand = dt.date.fromisoformat(haupt["stand"])
    h_text, h_klasse = zustand(haupt["loess"])
    klasse = duerre_klasse(haupt["perzentil"])
    zeit = jahreszeit_text(stand)

    # trockenste Jahre (vollständige Jahre) an der Hauptstation
    voll = [(j, n) for j, n in haupt["stress"] if j < stand.year]
    top = sorted(voll, key=lambda x: -x[1])[:5]
    top_text = ", ".join(f"{j} ({n} Tage)" for j, n in top)
    ohne = [j for j, n in voll if n == 0]
    dieses = next((n for j, n in haupt["stress"] if j == stand.year), 0)

    schichten = "".join(
        f'<div class="dm-schicht"><span class="dm-tiefe">{(k) * 10}–{(k + 1) * 10} cm</span>'
        f'<span class="dm-balken"><span style="width:{min(v or 0, 120) / 1.2:.0f}%"></span></span>'
        f'<span class="dm-sw">{de_zahl(v)} %</span></div>'
        for k, v in enumerate(haupt["schichten"]))

    zeilen = "".join(
        f"<tr><th scope=\"row\"><a href=\"#station-{s['id']}\">{e(namen[s['id']][0])}</a></th>"
        f"<td>{de_zahl(s['loess'])} %</td><td>{de_zahl(s['sand'])} %</td><td>{de_zahl(s['weizen'])} %</td>"
        f"<td>{de_zahl(s['median_heute'])} %</td><td>{e(duerre_klasse(s['perzentil']))}</td>"
        f"<td>{de_zahl(s['rr30'])} mm</td><td>{de_zahl(s['etp30'])} mm</td></tr>"
        for s in werte)

    # Regen: erste Station mit vollständiger Vergleichsreihe (Ummendorf hat Lücken)
    rr_st = next((s for s in werte if s["rr_jahresmittel"] and s["rrjahr_normal"]), haupt)
    rr_name = namen[rr_st["id"]][0]
    rr_jahr = rr_vergleich(rr_st["rrjahr"], rr_st["rrjahr_normal"])
    jahresmittel = rr_st["rr_jahresmittel"]
    md_jahresmittel = next((s["rr_jahresmittel"] for s in werte if s["id"] == 3126), None)

    erklaerung = ""
    if h_klasse in ("gut", "feucht") and haupt["perzentil"] < 30:
        erklaerung = (" Das ist kein Widerspruch: Für die Pflanzen reicht das Wasser im Moment. Aber im Herbst und Winter "
                      "füllt sich der Boden normalerweise wieder auf, und was jetzt fehlt, fehlt im Frühjahr als Reserve.")
    elif h_klasse in ("kritisch", "warnung") and haupt["perzentil"] >= 30:
        erklaerung = (" Für die Jahreszeit ist das nicht ungewöhnlich: Im Sommer ziehen Pflanzen und Verdunstung den Boden "
                      "fast jedes Jahr leer.")

    faq = [
        ("Wie trocken ist der Boden in der Börde gerade?",
         f"Am {de_datum(stand)} lag die Bodenfeuchte bei Ummendorf in 0 bis 60 cm Tiefe bei {de_zahl(haupt['loess'])} % "
         f"der nutzbaren Feldkapazität (Lössboden unter Gras). Das gilt als „{h_text}“. Im Vergleich der Jahre "
         f"{NORMAL[0]} bis {NORMAL[1]} entspricht das der Klasse „{klasse}“." + erklaerung),
        ("Was bedeutet „% nFK“?",
         "nFK steht für nutzbare Feldkapazität. Das ist die Wassermenge, die ein Boden gegen die Schwerkraft halten "
         "und die eine Pflanze tatsächlich aufnehmen kann. 100 % heißt: Der Boden ist so voll, wie er Wasser halten kann. "
         "0 % heißt: Das restliche Wasser ist so fest gebunden, dass Pflanzen welken."),
        ("Ab wann spricht man von Trockenstress?",
         "Als Faustregel gilt: Unter 50 % nFK wird das Wasser für viele Kulturen knapp, unter 30 % leiden die meisten "
         "Pflanzen unter Trockenstress und wachsen kaum noch."),
        ("Warum ist die Börde so trocken?",
         "Die Börde liegt im Regenschatten des Harzes. Westwinde regnen sich am Gebirge ab, östlich davon kommt weniger an. "
         + (f"In Magdeburg fielen {NORMAL[0]} bis {NORMAL[1]} im Mittel nur rund {de_zahl(md_jahresmittel)} mm Regen im Jahr. "
            if md_jahresmittel else "")
         + "Damit gehört die Gegend zu den trockensten in Deutschland."),
        ("Was ist der Unterschied zwischen Trockenheit und Dürre?",
         "Trockenheit beschreibt einen Zustand: Es ist wenig Wasser da. Von Dürre spricht man, wenn es deutlich trockener "
         "ist als üblich und das über längere Zeit. Darum vergleicht diese Seite die heutigen Werte mit denselben "
         f"Kalendertagen der Jahre {NORMAL[0]} bis {NORMAL[1]}."),
        ("Woher kommen die Daten und wie oft werden sie aktualisiert?",
         "Vom Deutschen Wetterdienst (DWD). Er berechnet die Bodenfeuchte täglich mit dem agrarmeteorologischen Modell "
         "AMBAV aus Wetterdaten der Stationen. Diese Seite lädt die Werte jeden Tag neu."),
    ]

    jsonld = [
        {"@context": "https://schema.org", "@type": "Dataset",
         "name": "Bodenfeuchte und Dürre im Landkreis Börde",
         "description": "Tägliche Bodenfeuchte (in % nutzbarer Feldkapazität) an DWD-Stationen in und am Landkreis Börde, "
                        f"mit Vergleich zu {NORMAL[0]}–{NORMAL[1]}, Niederschlag und Trockenstress-Tagen je Jahr.",
         "url": f"{BASIS_URL}/duerre/", "inLanguage": "de",
         "isAccessibleForFree": True, "dateModified": stand.isoformat(),
         "temporalCoverage": f"1991-01-01/{stand.isoformat()}",
         "spatialCoverage": {"@type": "Place", "name": "Landkreis Börde, Sachsen-Anhalt",
                             "geo": {"@type": "GeoShape", "box": "52.03 10.96 52.51 11.58"}},
         "creator": {"@type": "Organization", "name": "OK Lab Börde", "url": f"{BASIS_URL}/"},
         "isBasedOn": "https://opendata.dwd.de/climate_environment/CDC/derived_germany/soil/daily/",
         "license": "https://www.dwd.de/DE/service/copyright/copyright_artikel.html",
         "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                           "contentUrl": f"{BASIS_URL}/duerre/data.json"}]},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]

    faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in faq)
    knoepfe = "".join(
        f'<button type="button" data-station="{sid}" aria-pressed="{"true" if i == 0 else "false"}">{e(name)}</button>'
        for i, (sid, name, *_ ) in enumerate(STATIONEN))

    inhalt = f"""<header class="dm-kopf">
  <h1>Dürremonitor Börde: Wie trocken ist der Boden?</h1>
  <p class="lead">Tagesaktuelle Bodenfeuchte für den Landkreis Börde, berechnet vom Deutschen Wetterdienst. Mit Vergleich zu den Jahren {NORMAL[0]} bis {NORMAL[1]}, Regenmengen und Erklärungen, was den Wasserhaushalt der Börde bestimmt.</p>
</header>

<section class="dm-jetzt" aria-labelledby="dm-jetzt">
  <h2 id="dm-jetzt">Stand {de_datum(stand)}</h2>
  <p class="dm-satz">Im Lössboden bei Ummendorf liegt die Bodenfeuchte in den oberen 60 cm bei <strong>{de_zahl(haupt['loess'])} % nFK</strong>, das heißt <span class="dm-status dm-{h_klasse}">{e(h_text)}</span>. Üblich für {e(zeit)} sind {de_zahl(haupt['median_heute'])} %. Feuchter war es an diesem Tag in {haupt['trockener_als']} von {haupt['vergleich_jahre']} Jahren, das entspricht der Klasse <strong>{e(klasse)}</strong>.{erklaerung}</p>
  <div class="kacheln">
    <div class="kachel"><span class="zahl">{de_zahl(haupt['loess'])} %</span><span>Bodenfeuchte Lössboden</span></div>
    <div class="kachel"><span class="zahl">{de_zahl(haupt['sand'])} %</span><span>Bodenfeuchte Sandboden</span></div>
    <div class="kachel"><span class="zahl">{de_zahl(haupt['rr30'])} mm</span><span>Regen in 30 Tagen{(' · ' + rr_vergleich(haupt['rr30'], haupt['rr30_normal'])) if haupt['rr30_normal'] else ''}</span></div>
    <div class="kachel"><span class="zahl">{dieses}</span><span>Tage mit Trockenstress {stand.year}</span></div>
  </div>
</section>

<section aria-labelledby="dm-verlauf">
  <h2 id="dm-verlauf">Die letzten 12 Monate</h2>
  <div class="dm-filter" role="group" aria-label="Station wählen">{knoepfe}</div>
  <figure class="dm-figur">
    <div class="dm-chart" id="dm-chart-verlauf"></div>
    <figcaption>Bodenfeuchte in 0–60 cm Tiefe unter Gras, in % der nutzbaren Feldkapazität. Das graue Band zeigt, wie feucht der Boden am selben Kalendertag in 8 von 10 Jahren zwischen {NORMAL[0]} und {NORMAL[1]} war, die gestrichelte Linie den mittleren Wert. Unter der roten Linie bei 30 % herrscht Trockenstress.</figcaption>
  </figure>
</section>

<section aria-labelledby="dm-stationen">
  <h2 id="dm-stationen">Alle Stationen im Überblick</h2>
  <p>Der DWD rechnet die Bodenfeuchte für Wetterstationen. In und direkt am Landkreis Börde liegen vier davon. Ummendorf steht mitten im Lössgebiet und ist für die Börde am aussagekräftigsten.</p>
  <div class="dm-stationen">{''.join(stations_karte(s, *namen[s['id']][:2]) for s in werte)}</div>
  <div class="dm-tabelle-wrap">
  <table class="dm-tabelle">
    <caption>Bodenfeuchte (0–60 cm, % nFK) und Wasserbilanz der letzten 30 Tage</caption>
    <thead><tr><th scope="col">Station</th><th scope="col">Löss, Gras</th><th scope="col">Sand, Gras</th><th scope="col">Löss, Winterweizen</th><th scope="col">üblich ({NORMAL[0]}–{NORMAL[1]})</th><th scope="col">Einordnung</th><th scope="col">Regen</th><th scope="col">mögl. Verdunstung</th></tr></thead>
    <tbody>{zeilen}</tbody>
  </table>
  </div>
</section>

<section aria-labelledby="dm-schichten">
  <h2 id="dm-schichten">Wo im Boden steckt das Wasser?</h2>
  <p>Regen füllt den Boden von oben, Pflanzenwurzeln und Verdunstung leeren ihn von oben. Nach einem Schauer ist darum oft nur die oberste Schicht feucht, während es darunter trocken bleibt. Andersherum kann der Unterboden nach einem nassen Winter noch Wochen Wasser liefern, wenn oben schon alles staubt. So sieht es heute bei Ummendorf aus (Lössboden unter Gras):</p>
  <div class="dm-schichten">{schichten}</div>
</section>

<section aria-labelledby="dm-jahre">
  <h2 id="dm-jahre">Dürrejahre in der Börde seit 1991</h2>
  <p>Tage im Jahr, an denen der Lössboden bei Ummendorf unter 30 % nFK lag. Die meisten Trockenstress-Tage hatten {e(top_text)}.{(' Ganz ohne Trockenstress blieben ' + ', '.join(map(str, ohne[-6:])) + '.') if ohne else ''} {stand.year} sind es bisher {dieses} Tage.</p>
  <figure class="dm-figur">
    <div class="dm-chart" id="dm-chart-jahre"></div>
    <figcaption>Tage mit Bodenfeuchte unter 30 % nFK je Jahr (0–60 cm, Lössboden unter Gras). {stand.year} ist noch nicht vollständig.</figcaption>
  </figure>
</section>

<section class="dm-text" aria-labelledby="dm-faktoren">
  <h2 id="dm-faktoren">Was bestimmt, wie feucht der Boden ist?</h2>
  <p>Die Bodenfeuchte ist eine Bilanz: Was an Regen in den Boden sickert, minus was Pflanzen aufnehmen und was verdunstet. Mehrere Faktoren drehen an dieser Bilanz.</p>
  <h3>Niederschlag</h3>
  <p>Die wichtigste Quelle. Entscheidend ist nicht nur die Menge, sondern wie der Regen fällt. Landregen über mehrere Tage sickert tief ein. Ein Starkregen nach langer Trockenheit fließt zu einem großen Teil oberflächlich ab, weil ausgetrockneter Boden Wasser erst einmal schlecht aufnimmt. {('In ' + rr_name + ' fielen ' + str(NORMAL[0]) + ' bis ' + str(NORMAL[1]) + ' im Mittel ' + de_zahl(jahresmittel) + ' mm im Jahr. ') if jahresmittel else ''}{('Seit Jahresbeginn ' + str(stand.year) + ' waren es dort ' + de_zahl(rr_st['rrjahr']) + ' mm, ' + rr_jahr + ' für diesen Zeitraum.') if rr_jahr else ''}</p>
  <h3>Verdunstung: Sonne, Wärme, Wind</h3>
  <p>Je wärmer, sonniger, windiger und trockener die Luft, desto mehr Wasser verdunstet über Boden und Blätter. An einem heißen Sommertag können das 5 bis 6 mm sein, im Winter fast nichts. Darum füllt sich der Boden meist im Winterhalbjahr wieder auf und wird im Sommer leergezogen, selbst wenn es regelmäßig regnet. In den letzten 30 Tagen hätten bei Ummendorf bis zu {de_zahl(haupt['etp30'])} mm verdunsten können (potenzielle Verdunstung über Gras).</p>
  <h3>Bodenart</h3>
  <p>Der Börde-Boden ist berühmt: Löss, auf dem sich Schwarzerde gebildet hat. Er besteht aus feinen Schluffkörnern mit vielen mittelgroßen Poren, die Wasser lange halten und an Wurzeln wieder abgeben. Ein Lössboden kann auf einem Meter Tiefe rund 200 Liter pflanzenverfügbares Wasser je Quadratmeter speichern, ein Sandboden nur ein Drittel davon. Deshalb bringt die Börde trotz wenig Regen Spitzenerträge, und deshalb trocknen die sandigen Böden im Norden des Landkreises, etwa rund um die Letzlinger Heide, viel schneller aus. Der Monitor zeigt beide Bodenarten.</p>
  <h3>Pflanzen und Jahreszeit</h3>
  <p>Pflanzen sind die größten Wasserverbraucher. Wintergetreide wächst ab dem Frühjahr kräftig und zieht im Mai und Juni am meisten Wasser, Mais und Zuckerrüben erst im Hochsommer. Unter einem dichten Bestand trocknet der Boden schneller aus als unter kurzem Gras. Nach der Ernte und im Winter ruht der Verbrauch.</p>
  <h3>Grundwasser und Gelände</h3>
  <p>In Senken und Flussauen wie an Ohre, Aller und Bode reicht das Grundwasser teils bis an die Wurzeln heran. Auf Kuppen und Hängen fließt Regen dagegen schneller ab. Die Stationswerte gelten deshalb für einen ebenen Standort ohne Grundwasseranschluss.</p>
  <h3>Klimawandel</h3>
  <p>Höhere Temperaturen verlängern die Vegetationszeit und erhöhen die Verdunstung. Selbst bei gleicher Regenmenge bleibt dann weniger im Boden. Dazu kommen längere Trockenphasen im Sommer und mehr Starkregen, der schlecht einsickert. Die Jahre 2018 bis 2020 und 2022 haben gezeigt, wie empfindlich selbst die Börde darauf reagiert.</p>
</section>

<section class="dm-text" aria-labelledby="dm-folgen">
  <h2 id="dm-folgen">Was Trockenheit in der Börde bedeutet</h2>
  <ul>
    <li><strong>Landwirtschaft:</strong> Weizen, Gerste, Zuckerrüben und Raps sind die wichtigsten Kulturen. Fehlt im Frühjahr und Frühsommer Wasser, sinken Erträge und Qualität.</li>
    <li><strong>Wald und Stadtbäume:</strong> Bäume zehren über Jahre von den Reserven im Unterboden. Mehrere trockene Jahre hintereinander schwächen sie, Schädlinge haben dann leichtes Spiel.</li>
    <li><strong>Gärten:</strong> Wer weiß, wie es im Boden aussieht, gießt gezielter: lieber selten und durchdringend als täglich ein bisschen.</li>
    <li><strong>Grundwasser und Gewässer:</strong> Grundwasser bildet sich fast nur im Winterhalbjahr, wenn der Boden voll ist und Wasser nach unten durchsickert. Bleibt der Boden auch im Winter trocken, fehlt diese Neubildung.</li>
    <li><strong>Brandgefahr:</strong> Trockene Böden und Vegetation erhöhen die Gefahr von Feld- und Waldbränden. Aktuelle Warnstufen gibt der <a href="https://www.dwd.de/DE/leistungen/waldbrandgef/waldbrandgef.html">Waldbrandgefahrenindex des DWD</a>.</li>
  </ul>
</section>

<section class="dm-text" aria-labelledby="dm-faq">
  <h2 id="dm-faq">Häufige Fragen</h2>
  <div class="dm-faq">{faq_html}</div>
</section>

<section class="dm-text" aria-labelledby="dm-daten">
  <h2 id="dm-daten">Über die Daten</h2>
  <p>Die Werte sind keine Messungen im Feld, sondern Modellrechnungen des DWD (Modell AMBAV) aus den Wetterdaten der jeweiligen Station: Niederschlag, Temperatur, Luftfeuchte, Wind und Strahlung. Gerechnet wird für zwei Standardböden, lehmigen Schluff (entspricht dem Löss der Börde) und lehmigen Sand, und verschiedene Pflanzenbestände. Gras gilt als Referenz. Die Werte beziehen sich auf eine ebene Fläche ohne Grundwassereinfluss. Ein einzelner Acker kann deshalb deutlich abweichen, die Größenordnung und der Verlauf stimmen aber gut.</p>
  <p>Die Einordnung in Dürreklassen lehnt sich an den <a href="https://www.ufz.de/duerremonitor">Dürremonitor des Helmholtz-Zentrums für Umweltforschung (UFZ)</a> an: Liegt die Bodenfeuchte im unteren Fünftel der Vergleichsjahre, gilt das als Dürre. Der UFZ rechnet flächendeckend und bis 1,8 m Tiefe, diese Seite nutzt die Stationswerte des DWD für die oberen 60 cm und vergleicht mit {NORMAL[0]}–{NORMAL[1]}.</p>
  <p>Alle Werte gibt es als <a href="/duerre/data.json">JSON-Datei</a>. Aktualisiert wird täglich.</p>
</section>"""

    quelle = ('Daten: <a href="https://opendata.dwd.de/climate_environment/CDC/">Deutscher Wetterdienst</a>, '
              'berechnete Bodenfeuchte (AMBAV) und Klima-Tageswerte, verändert und ausgewertet. Ohne Gewähr.')
    html = seite(
        titel="Dürremonitor Börde: Bodenfeuchte aktuell | OK Lab Börde",
        beschreibung=(f"Wie trocken ist der Boden in der Börde? Tagesaktuelle Bodenfeuchte vom DWD, Vergleich mit "
                      f"{NORMAL[0]}–{NORMAL[1]}, Dürrejahre seit 1991 und was den Wasserhaushalt bestimmt."),
        pfad="/duerre/", inhalt=inhalt, brotkrumen=[("Start", "/"), ("Dürremonitor", None)], jsonld=jsonld,
        extra_head='<link rel="stylesheet" href="/assets/duerre.css">\n  <script defer src="/assets/duerre.js"></script>',
        quelle=quelle)
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(html, "utf-8", newline="\n")

    daten = {"stand": stand.isoformat(), "normal": list(NORMAL), "quelle": "Deutscher Wetterdienst (DWD), opendata.dwd.de",
             "stationen": [{**{k: v for k, v in s.items()}, "name": namen[s["id"]][0], "lat": namen[s["id"]][2],
                            "lon": namen[s["id"]][3]} for s in werte]}
    (OUT / "data.json").write_text(json.dumps(daten, ensure_ascii=False, separators=(",", ":")), "utf-8", newline="\n")


def main() -> None:
    werte = []
    for sid, name, *_ in STATIONEN:
        s = auswerten(sid)
        print(f"{name}: {s['stand']} Löss {s['loess']} % nFK, Sand {s['sand']} %, Perzentil {s['perzentil']}, "
              f"Regen 30 T {s['rr30']} mm (normal {s['rr30_normal'] and round(s['rr30_normal'])})")
        werte.append(s)
    erzeugen(werte)
    print("geschrieben:", OUT / "index.html")


if __name__ == "__main__":
    main()
