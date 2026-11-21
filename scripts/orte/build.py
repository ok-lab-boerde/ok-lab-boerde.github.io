"""Erzeugt aus den Rohdaten in scripts/orte/.cache/ die Seiten unter /betriebe/ und /orte/ sowie sitemap.xml.

Aufruf:  python scripts/orte/build.py      (vorher: python scripts/orte/fetch.py)
Nur Standardbibliothek. Ausgabe ist deterministisch: gleiche Daten ergeben gleiche Dateien.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo  # noqa: E402
import oeffnungszeiten as oz  # noqa: E402
from seiten import BASIS_URL, e, karte_div, liste, seite  # noqa: E402

HIER = Path(__file__).resolve().parent
ROOT = HIER.parents[1]
CACHE = HIER / ".cache"
OUT_BETRIEBE = ROOT / "betriebe"
OUT_ORTE = ROOT / "orte"
RESERVIERT = {"branche", "data", "ueber-die-daten", "karte"}


# ---------------------------------------------------------------- Hilfen
def slug(text: str) -> str:
    t = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:60].strip("-") or "eintrag"


def lade(name: str) -> dict:
    return json.loads((CACHE / name).read_text(encoding="utf-8"))


def pos(el: dict) -> tuple[float, float] | None:
    if "lat" in el:
        return el["lon"], el["lat"]
    if "center" in el:
        return el["center"]["lon"], el["center"]["lat"]
    return None


def schreibe(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8", newline="\n")


def tel_link(nr: str) -> str:
    return "tel:" + re.sub(r"[^0-9+]", "", nr.split(";")[0])


def web_link(url: str) -> str:
    url = url.split(";")[0].strip()
    return url if re.match(r"^https?://", url) else "https://" + url


def zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


ROLLSTUHL = {"yes": "rollstuhlgerecht", "limited": "eingeschränkt rollstuhlgerecht", "no": "nicht rollstuhlgerecht"}


# ---------------------------------------------------------------- Gebiete
def gemeinden_laden() -> list[dict]:
    fc = lade("gemeinden_vg250.json")
    out = []
    for f in fc["features"]:
        p = f["properties"]
        polys = geo.geojson_zu_polys(f["geometry"])
        out.append({"ags": p["ags"], "name": p["gen"], "polys": polys, "bbox": geo.bbox(polys)})
    out.sort(key=lambda g: g["name"])
    vergeben = set()
    for g in out:
        s = slug(g["name"])
        g["slug"] = s if s not in vergeben else f"{s}-{g['ags'][-3:]}"
        vergeben.add(g["slug"])
    return out


def ortsteile_laden(gemeinden: list[dict]) -> None:
    rels = lade("ortsteile.json")["elements"]
    for g in gemeinden:
        g["ortsteile"] = []
    for r in sorted(rels, key=lambda r: r["id"]):
        polys = geo.ringe_aus_osm(r.get("members", []))
        if not polys:
            continue
        x, y = geo.innerer_punkt(polys)
        for g in gemeinden:
            if geo.punkt_in_multipolygon(x, y, g["polys"]):
                flaeche = sum(geo.flaeche_und_schwerpunkt(p[0])[0] for p in polys)
                g["ortsteile"].append({"name": r["tags"].get("name", "?"), "osm": r["id"], "polys": polys,
                                       "bbox": geo.bbox(polys), "flaeche": flaeche, "level": r["tags"].get("admin_level")})
                break
    for g in gemeinden:
        g["ortsteile"].sort(key=lambda o: o["name"])
        vergeben = set(RESERVIERT)
        for o in g["ortsteile"]:
            s = slug(o["name"])
            o["slug"] = s if s not in vergeben else f"{s}-{o['osm']}"
            vergeben.add(o["slug"])


def verorten(lon: float, lat: float, gemeinden: list[dict]) -> tuple[dict | None, dict | None]:
    for g in gemeinden:
        b = g["bbox"]
        if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and geo.punkt_in_multipolygon(lon, lat, g["polys"]):
            treffer = [o for o in g["ortsteile"] if o["bbox"][0] <= lon <= o["bbox"][2] and o["bbox"][1] <= lat <= o["bbox"][3]
                       and geo.punkt_in_multipolygon(lon, lat, o["polys"])]
            return g, (min(treffer, key=lambda o: o["flaeche"]) if treffer else None)
    return None, None


# ---------------------------------------------------------------- Betriebe
def betriebe_laden(gemeinden: list[dict]) -> list[dict]:
    cfg = json.loads((HIER / "branchen.json").read_text(encoding="utf-8"))
    aus = {f"{t}/{i}" for t, i in (x.split("/") for x in
                                   json.loads((HIER / "ausschluss.json").read_text(encoding="utf-8"))["objekte"])}
    ausschl = [tuple(x) for x in cfg["ausschliessen"]]
    betriebe = []
    for el in lade("betriebe.json")["elements"]:
        t = el.get("tags", {})
        key = f"{el['type']}/{el['id']}"
        if key in aus or any(t.get(k) == v for k, v in ausschl):
            continue
        name = t.get("name") or ("Automat: " + t.get("operator", "") if t.get("amenity") == "vending_machine" and t.get("operator") else None)
        if not name:
            continue
        p = pos(el)
        if not p:
            continue
        branche = schluessel = None
        for r in cfg["regeln"]:
            if r["schluessel"] in t and (r["wert"] == "*" or t[r["schluessel"]] == r["wert"]):
                branche, schluessel = r["branche"], r["schluessel"]
                break
        if not branche:
            continue
        wert = t[schluessel]
        detail = cfg["details"].get(schluessel, {}).get(wert) or {
            "shop": "Geschäft", "craft": "Handwerksbetrieb", "office": "Büro", "healthcare": "Gesundheit",
            "tourism": "Unterkunft"}.get(schluessel, wert.replace("_", " ").capitalize())
        g, o = verorten(p[0], p[1], gemeinden)
        if not g:
            continue
        strasse = " ".join(x for x in (t.get("addr:street") or t.get("addr:place"), t.get("addr:housenumber")) if x)
        ortzeile = " ".join(x for x in (t.get("addr:postcode"), t.get("addr:city")) if x)
        oh = t.get("opening_hours")
        betriebe.append({
            "osm": key, "name": name, "branche": branche, "branche_name": cfg["branchen"][branche], "detail": detail,
            "lon": round(p[0], 5), "lat": round(p[1], 5), "gemeinde": g, "ortsteil": o,
            "strasse": strasse, "ortzeile": ortzeile,
            "telefon": t.get("phone") or t.get("contact:phone") or t.get("contact:mobile"),
            "website": t.get("website") or t.get("contact:website") or t.get("url"),
            "email": t.get("email") or t.get("contact:email"),
            "oh": oh, "woche": oz.parse(oh), "rollstuhl": ROLLSTUHL.get(t.get("wheelchair", "")),
        })
    betriebe.sort(key=lambda b: (b["gemeinde"]["slug"], b["name"].lower(), b["osm"]))
    vergeben: dict[str, set] = defaultdict(lambda: set(RESERVIERT))
    for b in betriebe:
        gs = b["gemeinde"]["slug"]
        s = slug(b["name"])
        if s in vergeben[gs] and b["ortsteil"]:
            s = f"{s}-{slug(b['ortsteil']['name'])}"
        if s in vergeben[gs]:
            s = f"{slug(b['name'])}-{b['osm'].replace('/', '-')}"
        vergeben[gs].add(s)
        b["slug"] = s
        b["url"] = f"/betriebe/{gs}/{s}/"
        b["ort"] = b["ortsteil"]["name"] if b["ortsteil"] else b["gemeinde"]["name"]
        b["index"] = sum(bool(b[k]) for k in ("oh", "telefon", "website", "email")) >= 2
    return betriebe


# ---------------------------------------------------------------- Steckbrief-Objekte
def poi_kategorie(t: dict) -> str | None:
    if t.get("amenity") == "fire_station":
        return "feuerwehr"
    if t.get("amenity") in ("kindergarten", "childcare"):
        return "kita"
    if t.get("amenity") == "school":
        return "schule"
    if t.get("amenity") == "library":
        return "bibliothek"
    if t.get("amenity") == "townhall":
        return "rathaus"
    if t.get("highway") == "bus_stop":
        return "haltestelle"
    if t.get("railway") in ("station", "halt"):
        return "bahnhof"
    if t.get("leisure") == "playground":
        return "spielplatz"
    if "club" in t or t.get("office") == "association":
        return "verein"
    if t.get("leisure") in ("sports_centre", "stadium", "sports_hall", "swimming_pool", "pitch", "golf_course", "horse_riding"):
        return "sport"
    if t.get("tourism") or t.get("historic") or t.get("leisure") in ("bathing_place", "beach_resort", "nature_reserve", "park") \
            or t.get("natural") == "beach":
        return "ausflug"
    return None


def pois_laden(gemeinden: list[dict]) -> list[dict]:
    out = []
    for el in lade("poi.json")["elements"]:
        t = el.get("tags", {})
        k = poi_kategorie(t)
        p = pos(el)
        if not k or not p:
            continue
        g, o = verorten(p[0], p[1], gemeinden)
        if not g:
            continue
        out.append({"kat": k, "name": t.get("name"), "osm": f"{el['type']}/{el['id']}", "lon": p[0], "lat": p[1],
                    "gemeinde": g, "ortsteil": o, "sport": t.get("sport")})
    out.sort(key=lambda x: ((x["name"] or "~").lower(), x["osm"]))
    return out


# ---------------------------------------------------------------- Lab-Daten je Gemeinde
def lab_daten() -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(dict)
    ew = ROOT / "energiewende" / "data.json"
    if ew.exists():
        d = json.loads(ew.read_text(encoding="utf-8"))
        for g in d.get("gemeinden", []):
            if g.get("schluessel"):
                out[g["schluessel"]]["energie"] = {"solar": g.get("solar", 0), "wind": g.get("wind", 0),
                                                   "biomasse": g.get("biomasse", 0), "stand": d.get("stand")}
    ua = ROOT / "unfallatlas" / "data" / "unfaelle.json"
    if ua.exists():
        d = json.loads(ua.read_text(encoding="utf-8"))
        f = {n: i for i, n in enumerate(d["felder"])}
        jahre = sorted({u[f["jahr"]] for u in d["unfaelle"]})
        z = Counter("15083" + u[f["gemeinde"]] for u in d["unfaelle"])
        rad = Counter("15083" + u[f["gemeinde"]] for u in d["unfaelle"] if u[f["beteiligt"]] & d["bits"]["rad"])
        for ags, n in z.items():
            out[ags]["unfaelle"] = {"anzahl": n, "rad": rad.get(ags, 0), "von": jahre[0], "bis": jahre[-1]}
    return out


# ---------------------------------------------------------------- Seiten: Betrieb
def nachbarn(b: dict, alle: list[dict], n: int) -> list[tuple[dict, float]]:
    kand = [(x, geo.distanz_m(b["lon"], b["lat"], x["lon"], x["lat"])) for x in alle if x is not b]
    kand.sort(key=lambda t: t[1])
    return kand[:n]


def entfernung(m: float) -> str:
    return f"{round(m / 10) * 10:.0f} m" if m < 1000 else f"{m / 1000:.1f} km".replace(".", ",")


def hauptort(o: dict | None, g: dict) -> bool:
    """True, wenn der Ortsteil der namensgebende Hauptort ist (z. B. Oschersleben in Oschersleben (Bode))."""
    return not o or o["name"] == g["name"] or g["name"].startswith(o["name"] + " (")


def betrieb_seite(b: dict, je_gemeinde: dict[str, list], haltestellen: list[dict]) -> str:
    g, o = b["gemeinde"], b["ortsteil"]
    if hauptort(o, g):
        o = None
    ort_text = f"{o['name']} ({g['name']})" if o else g["name"]
    typ, oid = b["osm"].split("/")
    vorhanden = [w for w, k in (("Adresse", "strasse"), ("Öffnungszeiten", "oh"), ("Telefon", "telefon"), ("Website", "website")) if b[k]]
    beschreibung = f"{b['name']}, {b['detail']} in {ort_text}" + (f": {', '.join(vorhanden)}." if vorhanden else ".") + " Daten aus OpenStreetMap."

    if o:
        lage =(f'in <a href="/orte/{g["slug"]}/{o["slug"]}/">{e(o["name"])}</a>, einem Ortsteil von '
                f'<a href="/orte/{g["slug"]}/">{e(g["name"])}</a> im Landkreis Börde')
    else:
        lage = f'in <a href="/orte/{g["slug"]}/">{e(g["name"])}</a> im Landkreis Börde'
    gleiche = [x for x in je_gemeinde[g["slug"]] if x["branche"] == b["branche"] and x is not b]
    intro = (f'<p class="lead">{e(b["name"])} ist als <strong>{e(b["detail"])}</strong> {lage} in OpenStreetMap eingetragen. '
             f'In {e(g["name"])} sind dort {zahl(len(gleiche))} weitere Betriebe der Branche '
             f'<a href="/betriebe/{g["slug"]}/branche/{b["branche"]}/">{e(b["branche_name"])}</a> verzeichnet.</p>')

    fakten = []
    if b["strasse"] or b["ortzeile"]:
        fakten.append(("Adresse", e(", ".join(x for x in (b["strasse"], b["ortzeile"]) if x))))
    if b["telefon"]:
        fakten.append(("Telefon", f'<a href="{e(tel_link(b["telefon"]))}">{e(b["telefon"].split(";")[0])}</a>'))
    if b["website"]:
        w = web_link(b["website"])
        anzeige = re.sub(r"^https?://(www\.)?", "", w).rstrip("/")
        fakten.append(("Website", f'<a href="{e(w)}" rel="nofollow noopener">{e(anzeige)}</a>'))
    if b["email"]:
        fakten.append(("E-Mail", f'<a href="mailto:{e(b["email"].split(";")[0])}">{e(b["email"].split(";")[0])}</a>'))
    if b["rollstuhl"]:
        fakten.append(("Barrierefreiheit", e(b["rollstuhl"].capitalize())))
    fakten.append(("Branche", f'{e(b["branche_name"])} · {e(b["detail"])}'))
    fakten.append(("Route", f'<a href="https://www.openstreetmap.org/directions?route=%3B{b["lat"]}%2C{b["lon"]}" rel="nofollow">Route planen (OpenStreetMap)</a>'))
    fakten_html = '<dl class="fakten">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in fakten) + "</dl>"

    if b["woche"]:
        zeilen = "".join(f"<tr><th scope=\"row\">{t}</th><td>{z}</td></tr>" for t, z in oz.tabelle(b["woche"]))
        oh_html = (f'<section aria-labelledby="h-oz"><h2 id="h-oz">Öffnungszeiten</h2>'
                   f'<p class="jetzt" data-woche="{e(json.dumps(b["woche"], separators=(",", ":")))}"></p>'
                   f'<table class="oz">{zeilen}</table>'
                   f'<p class="klein">Ohne Gewähr. Feiertage und Sonderöffnungszeiten sind nicht berücksichtigt.</p></section>')
    elif b["oh"]:
        oh_html = (f'<section aria-labelledby="h-oz"><h2 id="h-oz">Öffnungszeiten</h2><p>{e(oz.roh_deutsch(b["oh"]))}</p>'
                   f'<p class="klein">Angabe aus OpenStreetMap, ohne Gewähr.</p></section>')
    else:
        oh_html = ('<section aria-labelledby="h-oz"><h2 id="h-oz">Öffnungszeiten</h2>'
                   '<p class="leer">In OpenStreetMap sind keine Öffnungszeiten eingetragen.</p></section>')

    nah_h = [(h, geo.distanz_m(b["lon"], b["lat"], h["lon"], h["lat"])) for h in haltestellen]
    nah_h = sorted((x for x in nah_h if x[1] <= 2000), key=lambda x: x[1])
    gesehen, oepnv = set(), []
    for h, d in nah_h:
        if h["name"] in gesehen:
            continue
        gesehen.add(h["name"])
        oepnv.append((h["name"], None, f'{"Bahnhof" if h["kat"] == "bahnhof" else "Bushaltestelle"}, {entfernung(d)}'))
        if len(oepnv) == 3:
            break
    oepnv_html = (f'<section aria-labelledby="h-oepnv"><h2 id="h-oepnv">Bus und Bahn in der Nähe</h2>'
                  f'{liste(oepnv, "Keine benannte Haltestelle im Umkreis von 2 km in OpenStreetMap.")}</section>')

    gleiche_liste = [(x["name"], x["url"], f'{x["detail"]}, {x["ort"]}') for x in gleiche[:8]]
    nah = [(x["name"], x["url"], f'{x["detail"]}, {entfernung(d)}') for x, d in nachbarn(b, je_gemeinde[g["slug"]], 6)]
    mehr_html = (f'<div class="zwei"><section aria-labelledby="h-gleich"><h2 id="h-gleich">{e(b["branche_name"])} in {e(g["name"])}</h2>'
                 f'{liste(gleiche_liste, "Keine weiteren Betriebe dieser Branche.")}'
                 f'<p><a href="/betriebe/{g["slug"]}/branche/{b["branche"]}/">Alle anzeigen →</a></p></section>'
                 f'<section aria-labelledby="h-nah"><h2 id="h-nah">In der Nähe</h2>{liste(nah)}'
                 f'<p><a href="/betriebe/{g["slug"]}/">Alle Betriebe in {e(g["name"])} →</a></p></section></div>')

    korrektur = (f'<aside class="korrektur" aria-labelledby="h-korr"><h2 id="h-korr">Daten fehlen oder sind falsch?</h2>'
                 f'<p>Alle Angaben stammen aus OpenStreetMap, einer freien Karte, die jede und jeder bearbeiten kann. '
                 f'Änderungen dort erscheinen hier nach der nächsten wöchentlichen Aktualisierung.</p>'
                 f'<ol><li><a href="https://www.openstreetmap.org/{typ}/{oid}">Eintrag in OpenStreetMap ansehen</a></li>'
                 f'<li><a href="https://www.openstreetmap.org/edit?{typ}={oid}">Eintrag bearbeiten</a> (kostenloses Konto nötig)</li>'
                 f'<li>Öffnungszeiten, Telefon oder Website ergänzen und speichern.</li></ol>'
                 f'<p><a href="/betriebe/ueber-die-daten/">Anleitung und weitere Möglichkeiten</a></p></aside>')

    karte = karte_div({"zentrum": [b["lat"], b["lon"]], "zoom": 16, "punkte": [[b["lat"], b["lon"], b["name"], None]]},
                      "260px", f"Lage von {b['name']}")
    jsonld = {"@context": "https://schema.org", "@type": "LocalBusiness", "name": b["name"], "url": f"{BASIS_URL}{b['url']}",
              "geo": {"@type": "GeoCoordinates", "latitude": b["lat"], "longitude": b["lon"]}}
    if b["strasse"] or b["ortzeile"]:
        jsonld["address"] = {"@type": "PostalAddress", "streetAddress": b["strasse"] or None,
                             "postalCode": (b["ortzeile"].split(" ")[0] if b["ortzeile"][:1].isdigit() else None),
                             "addressLocality": b["ortzeile"].split(" ", 1)[-1] if b["ortzeile"] else b["ort"], "addressCountry": "DE"}
        jsonld["address"] = {k: v for k, v in jsonld["address"].items() if v}
    if b["telefon"]:
        jsonld["telephone"] = b["telefon"].split(";")[0]
    if b["website"]:
        jsonld["sameAs"] = web_link(b["website"])
    if b["oh"] and b["woche"]:
        jsonld["openingHours"] = b["oh"]

    inhalt = (f'<article class="betrieb"><h1>{e(b["name"])}</h1><p class="untertitel">{e(b["detail"])} · {e(ort_text)}</p>'
              f'{intro}<div class="zwei">{fakten_html}{karte}</div>{oh_html}{oepnv_html}{mehr_html}{korrektur}</article>')
    titel = f"{b['name']} – {b['detail']} in {ort_text} | OK Lab Börde"
    return seite(titel=titel, beschreibung=beschreibung, pfad=b["url"], inhalt=inhalt, index=b["index"], karte=True, jsonld=jsonld,
                 brotkrumen=[("Start", "/"), ("Betriebe", "/betriebe/"), (g["name"], f"/betriebe/{g['slug']}/"), (b["name"], None)])


# ---------------------------------------------------------------- Seiten: Betriebe je Gemeinde / Branche
def betriebe_liste_html(bs: list[dict], mit_branche: bool = True) -> str:
    return liste([(x["name"], x["url"], f'{x["detail"]}, {x["ort"]}' if mit_branche else x["ort"]) for x in bs])


def gemeinde_betriebe_seite(g: dict, bs: list[dict], branchen: dict[str, str]) -> str:
    teile = []
    nach = defaultdict(list)
    for b in bs:
        nach[b["branche"]].append(b)
    inhalt_branchen = []
    for bid, bname in branchen.items():
        if nach[bid]:
            inhalt_branchen.append(f'<li><a href="#{bid}">{e(bname)}</a> ({zahl(len(nach[bid]))})</li>')
            teile.append(f'<section id="{bid}" aria-labelledby="h-{bid}"><h2 id="h-{bid}">{e(bname)} '
                         f'<span class="anzahl">{zahl(len(nach[bid]))}</span></h2>{betriebe_liste_html(nach[bid])}'
                         f'<p><a href="/betriebe/{g["slug"]}/branche/{bid}/">Nur {e(bname)} in {e(g["name"])} →</a></p></section>')
    karte = karte_div({"grenze": geo.polys_vereinfachen(g["polys"], 0.0005),
                       "punkte": [[b["lat"], b["lon"], b["name"], b["url"]] for b in bs], "cluster": True}, "380px",
                      f"Karte der Betriebe in {g['name']}")
    inhalt = (f'<h1>Betriebe in {e(g["name"])}</h1>'
              f'<p class="lead">In OpenStreetMap sind für {e(g["name"])} {zahl(len(bs))} Betriebe eingetragen: Läden, Handwerk, '
              f'Gastronomie, Gesundheit, Unterkünfte und Dienstleistungen. Mehr über den Ort im '
              f'<a href="/orte/{g["slug"]}/">Steckbrief {e(g["name"])}</a>.</p>'
              f'<ul class="sprung">{"".join(inhalt_branchen)}</ul>{karte}{"".join(teile)}')
    return seite(titel=f"Betriebe in {g['name']} (Landkreis Börde) | OK Lab Börde",
                 beschreibung=f"{zahl(len(bs))} Betriebe in {g['name']}: Läden, Handwerk, Gastronomie, Gesundheit und mehr, mit Öffnungszeiten aus OpenStreetMap.",
                 pfad=f"/betriebe/{g['slug']}/", inhalt=inhalt, karte=True,
                 brotkrumen=[("Start", "/"), ("Betriebe", "/betriebe/"), (g["name"], None)])


def branche_seite(g: dict, bid: str, bname: str, bs: list[dict]) -> str:
    details = Counter(b["detail"] for b in bs).most_common(5)
    detail_text = ", ".join(f"{d} ({n})" for d, n in details)
    karte = karte_div({"grenze": geo.polys_vereinfachen(g["polys"], 0.0005),
                       "punkte": [[b["lat"], b["lon"], b["name"], b["url"]] for b in bs]}, "320px",
                      f"Karte: {bname} in {g['name']}")
    inhalt = (f'<h1>{e(bname)} in {e(g["name"])}</h1>'
              f'<p class="lead">{zahl(len(bs))} Einträge in OpenStreetMap, darunter {e(detail_text)}.</p>'
              f'{karte}{betriebe_liste_html(bs)}'
              f'<p><a href="/betriebe/{g["slug"]}/">Alle Betriebe in {e(g["name"])} →</a></p>')
    return seite(titel=f"{bname} in {g['name']} – {zahl(len(bs))} Einträge | OK Lab Börde",
                 beschreibung=f"{bname} in {g['name']} im Landkreis Börde: {detail_text}. Adressen und Öffnungszeiten aus OpenStreetMap.",
                 pfad=f"/betriebe/{g['slug']}/branche/{bid}/", inhalt=inhalt, karte=True, index=len(bs) >= 3,
                 brotkrumen=[("Start", "/"), ("Betriebe", "/betriebe/"), (g["name"], f"/betriebe/{g['slug']}/"), (bname, None)])


# ---------------------------------------------------------------- Seiten: Orte
POI_TITEL = {"verein": "Vereine", "sport": "Sportstätten", "feuerwehr": "Feuerwehr", "kita": "Kitas", "schule": "Schulen",
             "bibliothek": "Bibliotheken", "haltestelle": "Bushaltestellen", "bahnhof": "Bahnhöfe", "ausflug": "Ausflugsziele",
             "spielplatz": "Spielplätze", "rathaus": "Rathaus und Verwaltung"}


def poi_liste(pois: list[dict], kat: str, mit_ort: bool) -> str:
    gesehen, eint = set(), []
    for p in pois:
        if (kat and p["kat"] != kat) or not p["name"]:
            continue
        schl = (p["name"], p["ortsteil"]["name"] if p["ortsteil"] else "")
        if schl in gesehen:
            continue
        gesehen.add(schl)
        typ, oid = p["osm"].split("/")
        zusatz = p["ortsteil"]["name"] if mit_ort and p["ortsteil"] else ""
        eint.append((p["name"], f"https://www.openstreetmap.org/{typ}/{oid}", zusatz))
    return liste(eint, "Keine benannten Einträge in OpenStreetMap.")


def ort_seite(g: dict, o: dict | None, bs: list[dict], pois: list[dict], lab: dict, branchen: dict[str, str]) -> tuple[str, bool]:
    name = o["name"] if o else g["name"]
    pfad = f"/orte/{g['slug']}/{o['slug']}/" if o else f"/orte/{g['slug']}/"
    nb = Counter(b["branche"] for b in bs)
    pk = Counter(p["kat"] for p in pois)
    halte = len({p["name"] for p in pois if p["kat"] == "haltestelle" and p["name"]})
    benannt = len(bs) + sum(1 for p in pois if p["name"] and p["kat"] not in ("haltestelle", "spielplatz"))
    if o:
        lead = (f'{e(name)} ist ein Ortsteil der Gemeinde <a href="/orte/{g["slug"]}/">{e(g["name"])}</a> im Landkreis Börde '
                f'in Sachsen-Anhalt. Dieser Steckbrief fasst zusammen, was OpenStreetMap über den Ort weiß.')
    else:
        teile = len(g["ortsteile"])
        lead = (f'{e(name)} ist eine Gemeinde im Landkreis Börde in Sachsen-Anhalt'
                + (f' mit {zahl(teile)} Ortsteilen' if teile else '') +
                '. Dieser Steckbrief fasst zusammen, was OpenStreetMap über den Ort weiß.')
    kacheln = [("Betriebe", len(bs)), ("Vereine", pk["verein"]), ("Kitas und Schulen", pk["kita"] + pk["schule"]),
               ("Bushaltestellen", halte), ("Spielplätze", pk["spielplatz"]), ("Ausflugsziele", pk["ausflug"])]
    kachel_html = '<div class="kacheln">' + "".join(
        f'<div class="kachel"><span class="zahl">{zahl(n)}</span><span>{e(t)}</span></div>' for t, n in kacheln) + "</div>"

    ortsteile_html = ""
    if not o and g["ortsteile"]:
        ortsteile_html = ('<section aria-labelledby="h-ot"><h2 id="h-ot">Ortsteile</h2><ul class="spalten">' +
                          "".join(f'<li><a href="/orte/{g["slug"]}/{x["slug"]}/">{e(x["name"])}</a></li>' for x in g["ortsteile"]) +
                          "</ul></section>")

    branchen_zeilen = "".join(
        f'<li><a href="/betriebe/{g["slug"]}/branche/{bid}/">{e(bn)}</a> <span class="zusatz">{zahl(nb[bid])}</span></li>'
        for bid, bn in branchen.items() if nb[bid]) if not o else ""
    if not bs:
        betr_liste = ('<p class="leer">In OpenStreetMap sind hier noch keine Betriebe eingetragen. '
                      '<a href="/betriebe/ueber-die-daten/">So lässt sich das ändern.</a></p>')
    elif not o:
        betr_liste = (f'<ul class="eintraege">{branchen_zeilen}</ul>'
                      f'<p><a href="/betriebe/{g["slug"]}/">Alle {zahl(len(bs))} Betriebe in {e(g["name"])} →</a></p>')
    else:
        betr_liste = liste([(b["name"], b["url"], b["detail"]) for b in bs])
    mit_ort = not o
    gesund = [b for b in bs if b["branche"] == "gesundheit"]

    abschnitte = [
        ("Betriebe", betr_liste),
        ("Vereine und Sport", poi_liste(pois, "verein", mit_ort) + "<h3>Sportstätten</h3>" + poi_liste(pois, "sport", mit_ort)),
        ("Kinder und Schule", "<h3>Kitas</h3>" + poi_liste(pois, "kita", mit_ort) + "<h3>Schulen</h3>" + poi_liste(pois, "schule", mit_ort)
         + (f'<p>Spielplätze in OpenStreetMap: {zahl(pk["spielplatz"])}</p>')),
        ("Gesundheit", liste([(b["name"], b["url"], f'{b["detail"]}, {b["ort"]}' if mit_ort else b["detail"]) for b in gesund],
                             "Keine Arztpraxen, Apotheken oder Therapien in OpenStreetMap eingetragen.")),
        ("Bus und Bahn", "<h3>Bahnhöfe</h3>" + poi_liste(pois, "bahnhof", mit_ort) +
         f"<h3>Bushaltestellen</h3><p>{zahl(halte)} benannte Haltestellen in OpenStreetMap.</p>"),
        ("Ausflugsziele", poi_liste(pois, "ausflug", mit_ort)),
        ("Feuerwehr und Verwaltung", poi_liste([p for p in pois if p["kat"] in ("feuerwehr", "rathaus")], None, mit_ort)),
    ]
    absch_html = "".join(f'<section aria-labelledby="h-{slug(t)}"><h2 id="h-{slug(t)}">{e(t)}</h2>{h}</section>' for t, h in abschnitte)

    lab_html = ""
    if lab:
        teile = []
        if "energie" in lab:
            en = lab["energie"]
            mw = [f'{str(round(en[k], 1)).replace(".", ",")} MW {n}' for k, n in (("solar", "Solar"), ("wind", "Wind"), ("biomasse", "Biomasse"))
                  if round(en[k], 1) > 0]
            if mw:
                aufz = mw[0] if len(mw) == 1 else ", ".join(mw[:-1]) + " und " + mw[-1]
                teile.append(f'<li><a href="/energiewende/">Energiewende-Monitor</a>: In der Gemeinde {e(g["name"])} sind '
                             f'{aufz} in Betrieb.</li>')
        if "unfaelle" in lab:
            u = lab["unfaelle"]
            rad = f', davon {zahl(u["rad"])} mit Fahrrad' if u["rad"] else ""
            teile.append(f'<li><a href="/unfallatlas/">Unfallatlas</a>: {zahl(u["anzahl"])} Unfälle mit Personenschaden '
                         f'{u["von"]}–{u["bis"]} in der Gemeinde {e(g["name"])}{rad}.</li>')
        lab_html = "" if not teile else f'<section aria-labelledby="h-lab"><h2 id="h-lab">Aus anderen Lab-Projekten</h2><ul class="eintraege">{"".join(teile)}</ul></section>'

    flaeche = o["polys"] if o else g["polys"]
    karte = karte_div({"grenze": geo.polys_vereinfachen(flaeche, 0.0003 if o else 0.0005),
                       "punkte": [[b["lat"], b["lon"], b["name"], b["url"]] for b in bs], "cluster": len(bs) > 60},
                      "380px", f"Karte von {name}")
    inhalt = (f'<h1>{e(name)}</h1><p class="untertitel">{"Ortsteil von " + e(g["name"]) if o else "Gemeinde"} · Landkreis Börde</p>'
              f'<p class="lead">{lead}</p>{kachel_html}{karte}{ortsteile_html}{absch_html}{lab_html}')
    index = (not o) or benannt >= 5
    krumen = [("Start", "/"), ("Orte", "/orte/"), (g["name"], f"/orte/{g['slug']}/" if o else None)]
    if o:
        krumen.append((o["name"], None))
    besch = (f"Steckbrief {name}" + (f" ({g['name']})" if o else "") +
             f": {zahl(len(bs))} Betriebe, Vereine, Kitas, Schulen, Bus und Bahn und Ausflugsziele im Landkreis Börde.")
    return seite(titel=f"{name}" + (f" ({g['name']})" if o else "") + " – Ortssteckbrief | OK Lab Börde", beschreibung=besch,
                 pfad=pfad, inhalt=inhalt, karte=True, index=index, brotkrumen=krumen), index


def orte_index(gemeinden: list[dict], je_gemeinde: dict[str, list], stand: str) -> str:
    zeilen = "".join(
        f'<li><a href="/orte/{g["slug"]}/"><strong>{e(g["name"])}</strong></a> '
        f'<span class="zusatz">{zahl(len(g["ortsteile"]))} Ortsteile · {zahl(len(je_gemeinde[g["slug"]]))} Betriebe</span></li>'
        for g in gemeinden)
    inhalt = (f'<h1>Orte in der Börde</h1><p class="lead">Steckbriefe für alle {len(gemeinden)} Gemeinden im Landkreis Börde und ihre '
              f'Ortsteile: Betriebe, Vereine, Kitas und Schulen, Gesundheit, Bus und Bahn und Ausflugsziele, '
              f'zusammengestellt aus OpenStreetMap. Datenstand: {e(stand)}.</p><ul class="eintraege gemeinden">{zeilen}</ul>')
    return seite(titel="Orte in der Börde – Steckbriefe aller Gemeinden | OK Lab Börde",
                 beschreibung="Steckbriefe aller Gemeinden und Ortsteile im Landkreis Börde mit Betrieben, Vereinen, Schulen, Bus und Bahn und Ausflugszielen.",
                 pfad="/orte/", inhalt=inhalt, brotkrumen=[("Start", "/"), ("Orte", None)])


def ueber_seite(stand: str, n_betriebe: int, n_seiten: int) -> str:
    inhalt = f"""<h1>Über die Daten</h1>
<p class="lead">Die Betriebe-Karte und die Ortssteckbriefe zeigen, was in <a href="https://www.openstreetmap.org/">OpenStreetMap</a> über den Landkreis Börde eingetragen ist. Wir ergänzen und erfinden nichts.</p>
<section aria-labelledby="h-her"><h2 id="h-her">Herkunft und Aktualisierung</h2>
<ul class="eintraege">
<li><strong>Betriebe, Vereine, Schulen, Haltestellen, Ausflugsziele, Ortsteilgrenzen:</strong> OpenStreetMap über die Overpass API, © OpenStreetMap-Mitwirkende, Lizenz <a href="https://opendatacommons.org/licenses/odbl/">ODbL</a>.</li>
<li><strong>Gemeindegrenzen:</strong> Verwaltungsgebiete 1:250 000 (VG250), © GeoBasis-DE / BKG, <a href="https://www.govdata.de/dl-de/by-2-0">Datenlizenz Deutschland – Namensnennung – 2.0</a>.</li>
<li><strong>Aktualisierung:</strong> einmal pro Woche automatisch. Datenstand: {e(stand)}. Zurzeit {zahl(n_betriebe)} Betriebe auf {zahl(n_seiten)} Seiten.</li>
<li><strong>Welche Betriebe:</strong> nur Einträge mit Namen aus den Bereichen Einkaufen, Handwerk, Essen und Trinken, Gesundheit, Übernachten, Dienstleistung sowie Hofläden und Automaten mit regionalen Produkten. Ämter, Kirchen und Vereine erscheinen nur in den Ortssteckbriefen.</li>
<li><strong>Öffnungszeiten:</strong> werden aus der OSM-Angabe gelesen. Feiertage, Ferien und saisonale Zeiten berücksichtigen wir nicht. Komplizierte Angaben zeigen wir als Text.</li>
</ul></section>
<section aria-labelledby="h-aendern"><h2 id="h-aendern">Eintrag ändern oder ergänzen</h2>
<p>Unsere Seiten spiegeln OpenStreetMap. Eine Änderung direkt bei uns würde bei der nächsten Aktualisierung überschrieben. So ändern Sie Ihren Eintrag dauerhaft:</p>
<ol class="schritte">
<li>Auf der Seite Ihres Betriebs auf „Eintrag bearbeiten“ klicken. Sie landen direkt beim richtigen Objekt in OpenStreetMap.</li>
<li>Ein kostenloses OpenStreetMap-Konto anlegen und anmelden.</li>
<li>Im Editor die Felder ergänzen, zum Beispiel Öffnungszeiten, Telefon, Website oder Rollstuhlzugang. Für Öffnungszeiten hilft der <a href="https://projets.pavie.info/yohours/">YoHours-Assistent</a>.</li>
<li>Speichern und kurz beschreiben, was geändert wurde. Spätestens nach einer Woche erscheint die Änderung hier.</li>
</ol>
<p>Fehlt Ihr Betrieb ganz, können Sie ihn auf <a href="https://www.openstreetmap.org/">openstreetmap.org</a> neu eintragen. Bitte nur Angaben eintragen, die öffentlich sein sollen.</p>
</section>
<section aria-labelledby="h-raus"><h2 id="h-raus">Nicht aufgeführt werden</h2>
<p>Wenn Ihr Betrieb hier nicht erscheinen soll, Sie aber nichts in OpenStreetMap ändern möchten, nehmen wir ihn auf eine Ausschlussliste. Schreiben Sie uns über die Kontaktmöglichkeiten im Bereich <a href="/#mitmachen">Mitmachen &amp; Kontakt</a>. Der Eintrag in OpenStreetMap selbst bleibt davon unberührt.</p>
</section>
<section aria-labelledby="h-such"><h2 id="h-such">Suchmaschinen</h2>
<p>Seiten von Betrieben mit mindestens zwei Angaben (Öffnungszeiten, Telefon, Website oder E-Mail) dürfen von Suchmaschinen aufgenommen werden. Seiten mit weniger Angaben sind für Suchmaschinen gesperrt, bis der Eintrag in OpenStreetMap ergänzt wird.</p>
</section>"""
    return seite(titel="Über die Daten – Betriebe und Orte in der Börde | OK Lab Börde",
                 beschreibung="Woher die Daten der Betriebe-Karte und Ortssteckbriefe stammen, wie oft sie aktualisiert werden und wie Betriebe ihren Eintrag ändern.",
                 pfad="/betriebe/ueber-die-daten/", inhalt=inhalt, brotkrumen=[("Start", "/"), ("Betriebe", "/betriebe/"), ("Über die Daten", None)])


# ---------------------------------------------------------------- Hauptprogramm
def aufraeumen() -> None:
    if OUT_ORTE.exists():
        for p in OUT_ORTE.iterdir():
            if p.name != "README.md":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    if OUT_BETRIEBE.exists():
        for p in OUT_BETRIEBE.iterdir():
            if p.is_dir() and p.name != "data":
                shutil.rmtree(p)


def main() -> None:
    cfg = json.loads((HIER / "branchen.json").read_text(encoding="utf-8"))
    branchen = cfg["branchen"]
    gemeinden = gemeinden_laden()
    ortsteile_laden(gemeinden)
    betriebe = betriebe_laden(gemeinden)
    pois = pois_laden(gemeinden)
    lab = lab_daten()
    osm_stand = lade("betriebe.json").get("osm3s", {}).get("timestamp_osm_base", "")[:10]

    # Datenstand nur weiterschreiben, wenn sich die Daten wirklich geändert haben
    kern = json.dumps([[b["osm"], b["name"], b["detail"], b["lat"], b["lon"], b["oh"], b["telefon"], b["website"], b["email"],
                        b["strasse"], b["ortzeile"], b["rollstuhl"]] for b in betriebe] +
                      [[p["osm"], p["name"], p["kat"]] for p in pois] +
                      [[g["ags"], [o["osm"] for o in g["ortsteile"]]] for g in gemeinden], ensure_ascii=False)
    hash_neu = hashlib.sha256(kern.encode()).hexdigest()[:16]
    stand_datei = OUT_BETRIEBE / "data" / "stand.json"
    alt = json.loads(stand_datei.read_text(encoding="utf-8")) if stand_datei.exists() else {}
    stand_iso = alt.get("datenstand") if alt.get("hash") == hash_neu else osm_stand
    stand_iso = stand_iso or date.today().isoformat()
    stand = date.fromisoformat(stand_iso).strftime("%d.%m.%Y")

    aufraeumen()
    je_gemeinde: dict[str, list] = defaultdict(list)
    for b in betriebe:
        je_gemeinde[b["gemeinde"]["slug"]].append(b)
    haltestellen = [p for p in pois if p["kat"] in ("haltestelle", "bahnhof") and p["name"]]
    sitemap: list[str] = ["/betriebe/", "/orte/", "/betriebe/ueber-die-daten/"]
    n_seiten = 0

    for b in betriebe:
        schreibe(ROOT / b["url"].strip("/") / "index.html", betrieb_seite(b, je_gemeinde, haltestellen))
        n_seiten += 1
        if b["index"]:
            sitemap.append(b["url"])
    for g in gemeinden:
        bs = je_gemeinde[g["slug"]]
        schreibe(OUT_BETRIEBE / g["slug"] / "index.html", gemeinde_betriebe_seite(g, bs, branchen))
        sitemap.append(f"/betriebe/{g['slug']}/")
        n_seiten += 1
        for bid, bname in branchen.items():
            sel = [b for b in bs if b["branche"] == bid]
            if sel:
                schreibe(OUT_BETRIEBE / g["slug"] / "branche" / bid / "index.html", branche_seite(g, bid, bname, sel))
                n_seiten += 1
                if len(sel) >= 3:
                    sitemap.append(f"/betriebe/{g['slug']}/branche/{bid}/")
        gp = [p for p in pois if p["gemeinde"] is g]
        html, _ = ort_seite(g, None, bs, gp, lab.get(g["ags"], {}), branchen)
        schreibe(OUT_ORTE / g["slug"] / "index.html", html)
        sitemap.append(f"/orte/{g['slug']}/")
        n_seiten += 1
        for o in g["ortsteile"]:
            ob = [b for b in bs if b["ortsteil"] is o]
            op = [p for p in gp if p["ortsteil"] is o]
            html, idx = ort_seite(g, o, ob, op, {}, branchen)
            schreibe(OUT_ORTE / g["slug"] / o["slug"] / "index.html", html)
            n_seiten += 1
            if idx:
                sitemap.append(f"/orte/{g['slug']}/{o['slug']}/")
    schreibe(OUT_ORTE / "index.html", orte_index(gemeinden, je_gemeinde, stand))
    schreibe(OUT_BETRIEBE / "ueber-die-daten" / "index.html", ueber_seite(stand, len(betriebe), n_seiten))

    # Daten für die Karte (kompakt)
    bl = list(branchen)
    karte = {
        "felder": ["name", "branche", "detail", "lat", "lon", "gemeinde", "ort", "url", "woche"],
        "branchen": [[k, v] for k, v in branchen.items()],
        "gemeinden": [[g["slug"], g["name"]] for g in gemeinden],
        "betriebe": [[b["name"], bl.index(b["branche"]), b["detail"], b["lat"], b["lon"],
                      gemeinden.index(b["gemeinde"]), b["ort"], b["url"], b["woche"]] for b in betriebe],
    }
    schreibe(OUT_BETRIEBE / "data" / "betriebe.json", json.dumps(karte, ensure_ascii=False, separators=(",", ":")) + "\n")
    schreibe(stand_datei, json.dumps({"datenstand": stand_iso, "hash": hash_neu, "betriebe": len(betriebe),
                                      "seiten": n_seiten, "gemeinden": len(gemeinden),
                                      "ortsteile": sum(len(g["ortsteile"]) for g in gemeinden)}, ensure_ascii=False, indent=1) + "\n")

    # Sitemap für die ganze Website
    fest = ["/", "/energiewende/", "/unfallatlas/"]
    urls = "".join(f"<url><loc>{BASIS_URL}{u}</loc></url>\n" for u in fest + sitemap)
    schreibe(ROOT / "sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')

    idx = sum(1 for b in betriebe if b["index"])
    print(f"{len(betriebe)} Betriebe ({idx} indexierbar), {len(pois)} weitere Objekte, {len(gemeinden)} Gemeinden, "
          f"{sum(len(g['ortsteile']) for g in gemeinden)} Ortsteile, {n_seiten} Seiten, Sitemap {len(fest) + len(sitemap)} URLs, Stand {stand}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
