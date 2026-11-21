"""Regional einkaufen in der Börde: Hofläden, Automaten, Märkte, Fleischereien, Bäckereien, Imker und Saisonstände.

Quelle: die Betriebe aus OpenStreetMap (über build.py). Eigene Anmeldungen gibt es bewusst nicht:
Betriebe tragen sich in OpenStreetMap ein, die Anleitung steht unter /regional/eintragen/.
Wird von build.py aufgerufen und schreibt nach /regional/.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import oeffnungszeiten as oz
from seiten import e, karte_div, seite


ARTEN = [("hofladen", "Hofladen"), ("automat", "Automat"), ("markt", "Wochenmarkt"), ("saison", "Saisonstand"),
         ("obst", "Obst und Gemüse"), ("fleischerei", "Fleischerei"), ("baeckerei", "Bäckerei"), ("imker", "Imkerei und Honig")]
ART_NAME = dict(ARTEN)
PRODUKTE = [("eier", "Eier"), ("milch", "Milch und Käse"), ("fleisch", "Fleisch und Wurst"), ("kartoffeln", "Kartoffeln"),
            ("gemuese", "Gemüse"), ("obst", "Obst"), ("spargel", "Spargel"), ("erdbeeren", "Erdbeeren"), ("honig", "Honig"),
            ("brot", "Brot und Backwaren"), ("getraenke", "Säfte und Getränke"), ("blumen", "Blumen und Pflanzen")]
PRODUKT_NAME = dict(PRODUKTE)
MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
STANDARD_PRODUKTE = {"fleischerei": ["fleisch"], "baeckerei": ["brot"], "imker": ["honig"], "obst": ["obst", "gemuese"]}
# OSM-Werte aus vending=*, produce=*, product=* -> Produkt
VENDING = {"milk": "milch", "dairy": "milch", "cheese": "milch", "eggs": "eier", "egg": "eier",
           "potatoes": "kartoffeln", "potato": "kartoffeln", "meat": "fleisch", "sausages": "fleisch", "sausage": "fleisch",
           "honey": "honig", "fruit": "obst", "apples": "obst", "apple": "obst", "cherries": "obst", "plums": "obst",
           "vegetables": "gemuese", "vegetable": "gemuese", "pumpkin": "gemuese", "pumpkins": "gemuese",
           "asparagus": "spargel", "strawberries": "erdbeeren", "strawberry": "erdbeeren", "bread": "brot",
           "juice": "getraenke", "cider": "getraenke", "flowers": "blumen", "plants": "blumen"}
OSM_MONATE = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
JAHRESZEIT = {"spring": [3, 4, 5], "summer": [6, 7, 8], "autumn": [9, 10, 11], "winter": [12, 1, 2]}

# Faustregel für die Börde, nach Wetter verschieden: Produkt -> Monate (1-12)
SAISON = [("Spargel", [4, 5, 6]), ("Erdbeeren", [5, 6, 7]), ("Kirschen", [6, 7]), ("Frühkartoffeln", [6, 7]),
          ("Kartoffeln aus der Ernte", [8, 9, 10]), ("Pflaumen", [8, 9]), ("Äpfel und Birnen", [8, 9, 10]),
          ("Kürbis", [9, 10]), ("Kohl", [9, 10, 11, 12]), ("Honig aus der Ernte", [6, 7, 8])]


def saison_aus_osm(b: dict) -> list[int]:
    """Monate aus seasonal=* oder Monatsangaben in opening_hours (z. B. "Apr-Jun Mo-Sa 09:00-18:00")."""
    t, monate = b["rtags"], set()
    for w in re.split(r"[;,]\s*", t.get("seasonal", "")):
        monate.update(JAHRESZEIT.get(w, []))
    for a, z in re.findall(r"\b(%s)(?:\s*-\s*(%s))?\b" % ("|".join(OSM_MONATE), "|".join(OSM_MONATE)), b["oh"] or ""):
        i, j = OSM_MONATE.index(a) + 1, OSM_MONATE.index(z or a) + 1
        monate.update(range(i, j + 1) if i <= j else [*range(i, 13), *range(1, j + 1)])
    return sorted(monate) if len(monate) < 12 else []


def art_aus_osm(b: dict) -> str | None:
    t = b["rtags"]
    shop, craft, amenity = t.get("shop"), t.get("craft"), t.get("amenity")
    if shop in ("farm", "dairy", "cheese"):
        monate = saison_aus_osm(b)   # kurze Saison (bis 6 Monate) = Saisonstand, sonst Hofladen mit Saisonhinweis
        return "saison" if t.get("seasonal") not in (None, "no") or 0 < len(monate) <= 6 else "hofladen"
    if amenity == "vending_machine":
        return "automat"
    if amenity == "marketplace":
        return "markt"
    if shop == "greengrocer":
        return "obst"
    if shop == "butcher":
        return "fleischerei"
    if shop == "bakery" and "brand:wikidata" not in t:     # bundesweite Ketten ohne regionale Herstellung weglassen
        return "baeckerei"
    if craft == "beekeeper" or shop == "honey":
        return "imker"
    return None


def produkte_aus_osm(b: dict, art: str) -> list[str]:
    t = b["rtags"]
    p = set(STANDARD_PRODUKTE.get(art, []))
    for wert in re.split(r"[;,]\s*", t.get("vending", "") + ";" + t.get("product", "") + ";" + t.get("produce", "")):
        wert = wert.strip().lower()
        if wert in VENDING:
            p.add(VENDING[wert])
    return [k for k, _n in PRODUKTE if k in p]


def kurz_web(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def social_url(wert: str, basis: str) -> str:
    return wert if wert.startswith("http") else f"{basis}{wert.lstrip('@')}"


def nummer(nr: str) -> str:
    n = re.sub(r"[^\d+]", "", nr.split(";")[0])
    return "+49" + n[1:] if n.startswith("0") and not n.startswith("00") else n


def eintraege(betriebe: list[dict]) -> list[dict]:
    out = []
    for b in betriebe:
        art = art_aus_osm(b)
        if not art:
            continue
        name = b["name"] if not b["name"].startswith("Automat: ") else f"Regio-Automat ({b['name'][9:]})"
        out.append({
            "id": b["osm"].replace("/", "-"), "quelle": "osm", "name": name, "art": art, "produkte": produkte_aus_osm(b, art),
            "lat": b["lat"], "lon": b["lon"], "gemeinde": b["gemeinde"], "ort": b["ort"], "url": b["url"],
            "adresse": ", ".join(x for x in (b["strasse"], b["ortzeile"]) if x), "telefon": b["telefon"], "mobil": b["mobil"],
            "whatsapp": b["whatsapp"], "email": b["email"], "website": b["website"], "facebook": b["facebook"],
            "instagram": b["instagram"], "woche": b["woche"], "oh": b["oh"], "saison": saison_aus_osm(b), "beschreibung": "",
            "bio": b["rtags"].get("organic") in ("yes", "only"),
        })
    out.sort(key=lambda x: (x["name"].lower(), x["id"]))
    return out


def kontakt_knoepfe(x: dict) -> str:
    k = []
    if x["telefon"] or x["mobil"]:
        nr = x["telefon"] or x["mobil"]
        k.append(f'<a class="knopf" href="tel:{e(nummer(nr))}">Anrufen</a>')
    if x["whatsapp"]:
        k.append(f'<a class="knopf" href="https://wa.me/{e(nummer(x["whatsapp"]).lstrip("+"))}" rel="nofollow noopener">WhatsApp</a>')
    if x["email"]:
        adr = x["email"].split(";")[0].strip()
        betreff = "Anfrage über die Regional-Karte Börde"
        k.append(f'<a class="knopf" href="mailto:{e(adr)}?subject={e(betreff.replace(" ", "%20"))}">E-Mail</a>')
    if x["website"]:
        w = x["website"] if x["website"].startswith("http") else "https://" + x["website"]
        k.append(f'<a class="knopf" href="{e(w)}" rel="nofollow noopener">Website</a>')
    if x["facebook"]:
        k.append(f'<a class="knopf" href="{e(social_url(x["facebook"], "https://www.facebook.com/"))}" rel="nofollow noopener">Facebook</a>')
    if x["instagram"]:
        k.append(f'<a class="knopf" href="{e(social_url(x["instagram"], "https://www.instagram.com/"))}" rel="nofollow noopener">Instagram</a>')
    k.append(f'<a class="knopf" href="https://www.openstreetmap.org/directions?route=%3B{x["lat"]}%2C{x["lon"]}" rel="nofollow">Route</a>')
    return '<div class="knoepfe">' + "".join(k) + "</div>"


def saison_text(monate: list[int]) -> str:
    if not monate:
        return ""
    m = sorted(monate)
    if m == list(range(m[0], m[-1] + 1)):
        return f"{MONATE[m[0] - 1]}–{MONATE[m[-1] - 1]}" if len(m) > 1 else MONATE[m[0] - 1]
    return ", ".join(MONATE[i - 1] for i in m)


def karte_html(x: dict, gidx: dict) -> str:
    pidx = [i for i, (k, _n) in enumerate(PRODUKTE) if k in x["produkte"]]
    attrs = (f'data-art="{e(x["art"])}" data-g="{gidx[x["gemeinde"]["slug"]]}" data-p="{",".join(map(str, pidx))}" '
             f'data-i="{e(x["id"])}"' + (f' data-saison="{",".join(map(str, x["saison"]))}"' if x["saison"] else "")
             + (f' data-woche="{e(json.dumps(x["woche"], separators=(",", ":")))}"' if x["woche"] else ""))
    zeilen = [f'<span class="art">{e(ART_NAME[x["art"]])}</span>' + (' <span class="bio">Bio</span>' if x["bio"] else "")]
    titel = f'<h3><a href="{e(x["url"])}">{e(x["name"])}</a></h3>'
    info = [e(x["adresse"] or x["ort"])]
    if x["produkte"]:
        info.append("Angebot: " + e(", ".join(PRODUKT_NAME[p] for p in x["produkte"])))
    if x["saison"]:
        info.append(f'Saison: {saison_text(x["saison"])}')
    if x["woche"]:
        info.append('<span class="jetzt-kurz"></span>' + e(oz.roh_deutsch(x["oh"])))
    elif x.get("oh_text") or x["oh"]:
        info.append("Öffnungszeiten: " + e(x.get("oh_text") or oz.roh_deutsch(x["oh"])))
    return (f'<li class="reg-karte" id="r-{e(x["id"])}" {attrs}>{zeilen[0]}{titel}'
            f'<p class="info">{"<br>".join(info)}</p>{kontakt_knoepfe(x)}</li>')


ZELLE_AN = '<td class="an"><span aria-label="Saison">●</span></td>'


def saison_tabelle() -> str:
    kopf = "".join(f'<th scope="col"><abbr title="{n}">{n[0]}</abbr></th>' for n in
                   ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"])
    zeilen = "".join(
        f'<tr><th scope="row">{e(p)}</th>' + "".join(
            (ZELLE_AN if m in ms else "<td></td>") for m in range(1, 13))
        + "</tr>" for p, ms in SAISON)
    return (f'<div class="tabelle-scroll" tabindex="0" role="region" aria-label="Saisonkalender">'
            f'<table class="daten saison"><thead><tr><th scope="col">Produkt</th>{kopf}</tr></thead><tbody>{zeilen}</tbody></table></div>')


def uebersicht(liste: list[dict], gemeinden: list[dict], stand: str) -> str:
    gidx = {g["slug"]: i for i, g in enumerate(gemeinden)}
    zahl_art = {k: sum(1 for x in liste if x["art"] == k) for k, _n in ARTEN}
    art_haken = "".join(f'<label class="schalter"><input type="checkbox" name="art" value="{k}"> {n} <span class="zusatz">({zahl_art[k]})</span></label>'
                        for k, n in ARTEN)
    prod_opt = "".join(f'<option value="{i}">{n}</option>' for i, (_k, n) in enumerate(PRODUKTE))
    gem_opt = "".join(f'<option value="{i}">{e(g["name"])}</option>' for i, g in enumerate(gemeinden))
    punkte = [[x["lat"], x["lon"], x["name"], x["url"], x["id"]] for x in liste]
    karten = "".join(karte_html(x, gidx) for x in liste)
    punkte_json = json.dumps(punkte, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    inhalt = f"""<h1>Regional einkaufen in der Börde</h1>
<p class="lead">Hofläden, Milch- und Eierautomaten, Wochenmärkte, Saisonstände, Fleischereien, Bäckereien und Imkereien im Landkreis Börde. Bei jedem Eintrag können Sie direkt anrufen, schreiben oder die Route planen.</p>
<p class="klein">{len(liste)} Einträge aus OpenStreetMap. Datenstand: {e(stand)}.</p>
<aside class="aufruf"><strong>Sie verkaufen ab Hof, am Automaten oder am Feldrand und fehlen hier?</strong> Mit einem Eintrag in OpenStreetMap erscheinen Sie kostenlos auf dieser Karte und in vielen Karten-Apps. <a class="btn primary" href="/regional/eintragen/">So geht’s</a></aside>

<form class="suche" id="rg-filter" role="search" aria-label="Regionale Anbieter filtern">
  <label>Name oder Ort<input type="search" id="rg-q" placeholder="z. B. Eier, Wanzleben" autocomplete="off"></label>
  <label>Angebot<select id="rg-prod"><option value="">alles</option>{prod_opt}</select></label>
  <label>Gemeinde<select id="rg-gem"><option value="">alle Gemeinden</option>{gem_opt}</select></label>
  <label class="schalter"><input type="checkbox" id="rg-offen"> jetzt geöffnet</label>
  <fieldset class="haken"><legend>Art</legend>{art_haken}</fieldset>
</form>
<p class="treffer" id="rg-treffer" aria-live="polite"></p>
<div class="ok-karte" id="rg-karte" style="height:min(55vh,480px)" role="region" aria-label="Karte der regionalen Anbieter"></div>
<script type="application/json" id="rg-daten">{punkte_json}</script>
<ul class="reg-liste" id="rg-liste">{karten}</ul>

<section aria-labelledby="h-saison"><h2 id="h-saison">Was gibt es wann?</h2>
<p>Saisonkalender für die Börde als Faustregel. Je nach Wetter beginnt und endet die Saison früher oder später. Lagerware wie Kartoffeln und Äpfel gibt es oft bis ins Frühjahr.</p>
{saison_tabelle()}
</section>

<section aria-labelledby="h-daten"><h2 id="h-daten">Woher die Einträge stammen</h2>
<ul class="eintraege">
<li><strong>OpenStreetMap:</strong> Alle Einträge stammen aus der freien Weltkarte OpenStreetMap: Hofläden, Saisonstände, Automaten, Märkte, Fleischereien, Bäckereien (ohne bundesweite Ketten), Obst- und Gemüseläden und Imkereien. Fehlendes lässt sich dort ergänzen, siehe <a href="/regional/eintragen/">Anleitung</a> und <a href="/betriebe/karten-check/">Karten-Check</a>.</li>
<li>Wir sammeln selbst keine Daten von Betrieben. Was in OpenStreetMap steht, erscheint hier nach der nächsten wöchentlichen Aktualisierung.</li>
<li>Alle Angaben ohne Gewähr. Vor einer längeren Fahrt lohnt ein kurzer Anruf.</li>
</ul></section>"""
    return seite(titel="Hofläden und regional einkaufen in der Börde – Karte | OK Lab Börde",
                 beschreibung=f"{len(liste)} Hofläden, Automaten, Wochenmärkte, Saisonstände, Fleischereien, Bäckereien und Imker im Landkreis Börde, mit Telefon, Öffnungszeiten und Route.",
                 pfad="/regional/", inhalt=inhalt, karte=True, extra_head='<script src="/assets/regional.js" defer></script>',
                 brotkrumen=[("Start", "/"), ("Regional einkaufen", None)])


def anleitung_seite(liste: list[dict]) -> str:
    n_hof = sum(1 for x in liste if x["art"] in ("hofladen", "saison"))
    inhalt = f"""<h1>So kommt Ihr Hof auf die Karte</h1>
<p class="lead">Die Karte <a href="/regional/">Regional einkaufen</a> zeigt, was in <a href="https://www.openstreetmap.org/">OpenStreetMap</a> eingetragen ist, der freien Weltkarte, die jede und jeder bearbeiten darf. Wer dort steht, erscheint kostenlos bei uns und in Karten-Apps wie OsmAnd, Organic Maps oder Komoot. Zurzeit sind im Landkreis Börde erst {n_hof} Hofläden und Saisonstände eingetragen.</p>

<section aria-labelledby="h-schon"><h2 id="h-schon">1. Prüfen, ob Sie schon eingetragen sind</h2>
<p>Suchen Sie Ihren Betrieb auf der <a href="/regional/">Regional-Karte</a> oder im <a href="/betriebe/karten-check/">Karten-Check</a>. Dort sehen Sie auch, welche Angaben noch fehlen, und kommen mit „Eintrag bearbeiten“ direkt zum richtigen Punkt.</p>
</section>

<section aria-labelledby="h-ohne"><h2 id="h-ohne">2. Ohne Konto: Hinweis hinterlassen</h2>
<p>Der einfachste Weg. Er dauert etwas länger, weil Freiwillige den Hinweis eintragen.</p>
<ol class="schritte">
<li><a href="https://www.openstreetmap.org/note/new#map=11/52.2/11.35">Hinweis-Formular von OpenStreetMap öffnen</a> und die Karte bis zu Ihrem Hof heranzoomen.</li>
<li>Den Marker genau auf den Verkaufsstand oder die Hofeinfahrt ziehen.</li>
<li>In das Textfeld schreiben, was dort ist. Zum Beispiel: <em>„Hofladen Müller, verkauft Eier, Kartoffeln und Honig. Geöffnet Mo–Fr 9–18 Uhr, Sa 9–12 Uhr. Telefon 039xx 12345.“</em></li>
<li>„Hinweis hinzufügen“ klicken. Der Hinweis ist öffentlich sichtbar. Bitte nur Angaben schreiben, die auch auf der Karte stehen sollen.</li>
</ol>
</section>

<section aria-labelledby="h-selbst"><h2 id="h-selbst">3. Selbst eintragen</h2>
<p>Dauert etwa zehn Minuten und ist sofort in OpenStreetMap gespeichert. Bei uns erscheint der Eintrag nach der nächsten wöchentlichen Aktualisierung.</p>
<ol class="schritte">
<li>Auf openstreetmap.org <a href="https://www.openstreetmap.org/user/new">ein kostenloses Konto anlegen</a> und anmelden.</li>
<li>Zur eigenen Adresse zoomen und oben auf „Bearbeiten“ klicken. Es öffnet sich der Editor iD mit einer kurzen Einführung, die sich lohnt.</li>
<li>Oben auf „Punkt“ klicken und den Punkt auf den Verkaufsort setzen.</li>
<li>Links die passende Art suchen und auswählen (siehe Tabelle unten), zum Beispiel „Hofladen“.</li>
<li>Name, Öffnungszeiten, Telefon, Website und Adresse in die Felder schreiben. Für Öffnungszeiten hilft der <a href="https://projets.pavie.info/yohours/">YoHours-Assistent</a>.</li>
<li>Was Sie verkaufen, kommt in die Textansicht der Eigenschaften (Schalter „Textansicht“ unter „Eigenschaften“), zum Beispiel <code>produce=eggs;potatoes;honey</code>.</li>
<li>Oben auf „Speichern“ klicken und kurz beschreiben, was Sie eingetragen haben, etwa „Hofladen ergänzt“.</li>
</ol>
</section>

<section aria-labelledby="h-was"><h2 id="h-was">Was wo eingetragen wird</h2>
<div class="tabelle-scroll" tabindex="0" role="region" aria-label="Tabelle: Arten und OSM-Merkmale">
<table class="daten links"><thead><tr><th scope="col">Sie haben …</th><th scope="col">Im Editor auswählen</th><th scope="col">OSM-Merkmal</th></tr></thead><tbody>
<tr><th scope="row">Hofladen</th><td>Hofladen</td><td><code>shop=farm</code></td></tr>
<tr><th scope="row">Stand nur in der Saison (Spargel, Erdbeeren)</th><td>Hofladen, Öffnungszeiten mit Monaten</td><td><code>shop=farm</code>, <code>opening_hours=Apr-Jun Mo-Sa 09:00-18:00</code></td></tr>
<tr><th scope="row">Milch-, Eier- oder Kartoffelautomat</th><td>Verkaufsautomat</td><td><code>amenity=vending_machine</code>, <code>vending=milk;eggs</code></td></tr>
<tr><th scope="row">Imkerei mit Verkauf</th><td>Honigladen</td><td><code>shop=honey</code></td></tr>
<tr><th scope="row">Wochenmarkt</th><td>Marktplatz</td><td><code>amenity=marketplace</code>, Markttage als <code>opening_hours</code></td></tr>
<tr><th scope="row">Bio-Betrieb</th><td>Feld „Bio“</td><td><code>organic=only</code> oder <code>organic=yes</code></td></tr>
</tbody></table></div>
<p class="klein">Angebote im Merkmal <code>produce</code> oder <code>vending</code>, die wir erkennen: eggs (Eier), milk (Milch), cheese (Käse), potatoes (Kartoffeln), vegetables (Gemüse), fruit oder apples (Obst), asparagus (Spargel), strawberries (Erdbeeren), honey (Honig), meat oder sausages (Fleisch und Wurst), bread (Brot), juice (Saft), flowers (Blumen).</p>
</section>

<section aria-labelledby="h-tipps"><h2 id="h-tipps">Gut zu wissen</h2>
<ul class="eintraege">
<li><strong>Alles ist öffentlich:</strong> Was in OpenStreetMap steht, kann jeder sehen und weiterverwenden (Lizenz ODbL). Bitte keine privaten Telefonnummern oder Wohnadressen eintragen, die nicht öffentlich sein sollen.</li>
<li><strong>Änderungen:</strong> Öffnungszeiten ändern sich? Einfach wieder auf „Bearbeiten“ gehen. Bei uns ist die Änderung spätestens nach einer Woche sichtbar.</li>
<li><strong>Werbung und Bewertungen</strong> gehören nicht in OpenStreetMap, nur sachliche Angaben.</li>
<li><strong>Hilfe:</strong> Fragen beantwortet die deutschsprachige OpenStreetMap-Gemeinschaft im <a href="https://community.openstreetmap.org/c/communities/de/">Forum</a>. Oder fragen Sie uns über den Bereich <a href="/#mitmachen">Mitmachen &amp; Kontakt</a>.</li>
</ul></section>"""
    return seite(titel="Hofladen in OpenStreetMap eintragen – Anleitung | OK Lab Börde",
                 beschreibung="Schritt für Schritt: So tragen Hofläden, Saisonstände, Automaten und Imker im Landkreis Börde sich kostenlos in OpenStreetMap ein und erscheinen auf der Regional-Karte.",
                 pfad="/regional/eintragen/", inhalt=inhalt,
                 brotkrumen=[("Start", "/"), ("Regional einkaufen", "/regional/"), ("So kommt Ihr Hof auf die Karte", None)])


def erzeugen(betriebe: list[dict], gemeinden: list[dict], stand: str, schreibe, out: Path) -> list[str]:
    """Schreibt /regional/ und gibt die URLs für die Sitemap zurück."""
    liste = eintraege(betriebe)
    schreibe(out / "index.html", uebersicht(liste, gemeinden, stand))
    schreibe(out / "eintragen" / "index.html", anleitung_seite(liste))
    return ["/regional/", "/regional/eintragen/"]
