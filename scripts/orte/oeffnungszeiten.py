"""Einfacher Parser für OSM-opening_hours.

Deckt die häufigen Fälle ab ("Mo-Fr 08:00-18:00; Sa 09:00-12:00", "24/7", "Mo,We 10:00-12:00,14:00-18:00",
"Su off", "PH off"). Alles mit Monaten, Wochen, Datumsangaben, Sonnenauf-/untergang oder offenen Enden
wird bewusst NICHT interpretiert: dann gibt parse() None zurück und die Seite zeigt den Rohtext.

Ergebnis: Liste mit 7 Einträgen (Montag .. Sonntag), je eine Liste von [start_minute, ende_minute].
Zeiten über Mitternacht werden auf den Folgetag umgebrochen.
"""
from __future__ import annotations

import re

TAGE = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
TAGE_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
KURZ_DE = {"Mo": "Mo", "Tu": "Di", "We": "Mi", "Th": "Do", "Fr": "Fr", "Sa": "Sa", "Su": "So", "PH": "Feiertage", "SH": "Schulferien"}

_ZEIT = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")
_TAG_TEIL = re.compile(r"^(Mo|Tu|We|Th|Fr|Sa|Su)(?:-(Mo|Tu|We|Th|Fr|Sa|Su))?$")


def _tage(selector: str) -> list[int] | None:
    out: list[int] = []
    for teil in selector.split(","):
        teil = teil.strip()
        if teil == "PH":
            continue  # Feiertage werden nicht ausgewertet
        m = _TAG_TEIL.match(teil)
        if not m:
            return None
        a = TAGE.index(m.group(1))
        b = TAGE.index(m.group(2)) if m.group(2) else a
        i = a
        while True:
            out.append(i)
            if i == b:
                break
            i = (i + 1) % 7
    return out


def _zeiten(text: str) -> list[tuple[int, int]] | None:
    out = []
    for teil in text.split(","):
        m = _ZEIT.match(teil.strip())
        if not m:
            return None
        h1, m1, h2, m2 = map(int, m.groups())
        if h1 > 24 or h2 > 48 or m1 > 59 or m2 > 59:
            return None
        out.append((h1 * 60 + m1, h2 * 60 + m2))
    return out


def parse(value: str | None) -> list[list[list[int]]] | None:
    if not value:
        return None
    value = value.strip()
    if value == "24/7":
        return [[[0, 1440]] for _ in range(7)]
    woche: list[list[list[int]]] = [[] for _ in range(7)]
    # Häufige Schreibweisen vereinheitlichen
    value = re.sub(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", r"\1-\2", value)          # "07:30- 09:30"
    value = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\s*,\s*(?=(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b)", r"\1,", value)  # "Mo, We"
    neue_regel = r"\s*,\s*(?=(Mo|Tu|We|Th|Fr|Sa|Su|PH)[A-Za-z,\-]*\s+(\d|off|closed))"
    value = re.sub(r"(?<=\d)" + neue_regel, "; ", value)                                              # "12:00, Sa 09:00"
    value = re.sub(r"(?<=off)" + neue_regel, "; ", value)
    value = re.sub(r"(?<=closed)" + neue_regel, "; ", value)
    regeln = [r.strip() for r in re.split(r";|\|\|", value) if r.strip()]
    if not regeln:
        return None
    for regel in regeln:
        if '"' in regel:
            return None
        teile = regel.split(None, 1)
        if _tage(teile[0]) is not None and (len(teile) == 1 or teile[1].strip()):
            tage = _tage(teile[0])
            rest = teile[1].strip() if len(teile) > 1 else ""
            if teile[0].strip() == "PH":
                continue  # "PH off" / "PH 10:00-12:00" ignorieren
        elif _zeiten(regel) is not None or regel in ("off", "closed"):
            tage, rest = list(range(7)), regel
        else:
            return None
        if not tage:
            continue
        if rest in ("off", "closed"):
            for t in tage:
                woche[t] = []
            continue
        if rest == "24/7" or rest == "00:00-24:00":
            zeiten = [(0, 1440)]
        else:
            zeiten = _zeiten(rest)
            if zeiten is None:
                return None
        for t in tage:
            woche[t] = []  # spätere Regel überschreibt frühere für diesen Tag
        for t in tage:
            for a, b in zeiten:
                if b > a:
                    woche[t].append([a, min(b, 1440)])
                    if b > 1440:
                        woche[(t + 1) % 7].append([0, b - 1440])
                elif b < a:  # über Mitternacht
                    woche[t].append([a, 1440])
                    woche[(t + 1) % 7].append([0, b])
    for tag in woche:
        tag.sort()
    if not any(woche):
        return None
    return woche


def zeit_text(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def tabelle(woche: list[list[list[int]]]) -> list[tuple[str, str]]:
    zeilen = []
    for i, tag in enumerate(woche):
        text = ", ".join(f"{zeit_text(a)}–{zeit_text(b)}" for a, b in tag) if tag else "geschlossen"
        zeilen.append((TAGE_DE[i], text.replace("–24:00", "–24:00")))
    return zeilen


def roh_deutsch(value: str) -> str:
    """Rohwert lesbarer machen, wenn der Parser aufgibt (nur Wochentage und off übersetzen)."""
    text = value
    for en, de in KURZ_DE.items():
        text = re.sub(rf"\b{en}\b", de, text)
    return text.replace("off", "geschlossen").replace(";", "; ")


if __name__ == "__main__":
    for t in ["Mo-Fr 08:00-18:00; Sa 09:00-12:00", "24/7", "Mo,We 10:00-12:00,14:00-18:00; PH off",
              "Tu-Su 17:00-01:00", "Apr-Oct Mo-Su 10:00-18:00", "Mo-Fr 07:00-12:00, 13:00-16:00", "Fr-Mo 10:00-14:00"]:
        print(t, "->", parse(t))
