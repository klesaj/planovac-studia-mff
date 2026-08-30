#!/usr/bin/env python3
"""Stahne a rozparsuje SIS stranky predmetu.

Pouziti:
    python3 tools/sis.py                 # obnovi data/sis.csv pro kody z data/predmety.csv
    python3 tools/sis.py NPFL140 NAIL002 # vypise detaily jednoho/vice predmetu

Stazene HTML se cachuje v zdroje/sis/<KOD>.html a znovu se nestahuje.
"""
import csv, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "zdroje", "sis")
URL = "https://is.cuni.cz/studium/predmety/index.php?do=predmet&kod={}"
FIELDS = ["kod", "nazev", "anglicky", "semestr", "kredity", "rozsah", "examinace",
          "stav", "forma", "pracoviste", "garant", "vyucujici", "neslucitelnost"]


def stahni(kod):
    path = os.path.join(CACHE, f"{kod}.html")
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        req = urllib.request.Request(URL.format(kod), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    return open(path, encoding="utf-8").read()


def text(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html))


def pole(t, label, stop):
    m = re.search(re.escape(label) + r":?\s*(.{0,400})", t)
    if not m:
        return ""
    val = m.group(1)
    for s in stop:
        val = val.split(s)[0]
    return val.strip(" :,")


def parsuj(kod):
    t = text(stahni(kod))
    # navigacni menu nahore obsahuje stejne popisky jako telo stranky
    i = t.find("Popis předmětu")
    if i > 0:
        t = t[i:]
    m = re.search(r"([^.>|]{3,70}?)\s+-\s+" + kod + r"\b", t)
    nazev = m.group(1).strip() if m else ""
    rozsah = pole(t, "Rozsah, examinace", ["Počet míst", "Maximální kapacita"])
    zk = re.search(r"\b(Z\+Zk|KZ|Zk|Z)\b\s*\[", rozsah)
    hodiny = re.search(r"(\d+/\d+)", rozsah)
    return {
        "kod": kod,
        "nazev": nazev,
        "semestr": pole(t, "Semestr", ["E-Kredity"]),
        "kredity": pole(t, "E-Kredity", ["Rozsah"]),
        "rozsah": hodiny.group(1) if hodiny else "",
        "examinace": zk.group(1) if zk else "",
        "garant": pole(t, "Garant", ["Vyučující", "Třída", "Kategorizace"]),
        "vyucujici": pole(t, "Vyučující", ["Třída", "Kategorizace", "Neslučitelnost",
                                           "Záměnnost", "Je ", "Výsledky anket",
                                           "Rozvrh", "Nástěnka", "Anotace", "Korekvizita"]),
        "neslucitelnost": pole(t, "Neslučitelnost", ["Záměnnost", "Je ", "Korekvizita", "Výsledky"]),
        "stav": pole(t, "Stav předmětu", ["Jazyk výuky", "Způsob výuky", "Další"]),
        "pracoviste": pole(t, "Zajišťuje", ["Fakulta"]),
        "forma": pole(t, "Podoba výuky", ["Zajišťuje", "Fakulta"]),
        "anglicky": pole(t, "Anglický název", ["Zajišťuje", "Podoba výuky"]),
    }


def main():
    if len(sys.argv) > 1:
        for kod in sys.argv[1:]:
            for k, v in parsuj(kod).items():
                print(f"{k:15} {v}")
            print("-" * 60)
        return
    src = os.path.join(ROOT, "data", "predmety.csv")
    kody = [r["kod"] for r in csv.DictReader(open(src, encoding="utf-8"))]
    out = os.path.join(ROOT, "data", "sis.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for kod in kody:
            w.writerow(parsuj(kod))
            print(".", end="", flush=True)
    print(f"\n{len(kody)} predmetu -> {out}")


if __name__ == "__main__":
    main()
