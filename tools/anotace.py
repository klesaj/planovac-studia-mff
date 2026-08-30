#!/usr/bin/env python3
"""Vytahne ze SIS stranek predmetu textovy popis (anotace, sylabus, ...).

SIS ma popisne sekce ulozene ve dvou jazykovych variantach vedle sebe:
    <div id="pamela_<KLIC>_CZE"> ... </div>
    <div id="pamela_<KLIC>_ENG"> ... </div>   (skryta, display:none)
Bere se JEN ceska varianta. Klice sekci: A=Anotace, C=Cil predmetu,
S=Sylabus, E=Podminky zakonceni, L=Literatura, M=Metody vyuky.

Na konci kazde sekce je jeste sedivy odstavec "Posledni uprava: ..." - ten
do textu nepatri a odrizne se.

Pouziti:
    python3 tools/anotace.py            # obnovi data/anotace.csv pro vrstvy A/B/C
    python3 tools/anotace.py NAIL002    # vypise sekce jednoho/vice predmetu

HTML se bere z cache zdroje/sis/<KOD>.html (stahne se, jen kdyz chybi).
"""
import argparse, csv, html as htmlmod, os, re, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "zdroje", "sis")
URL = "https://is.cuni.cz/studium/predmety/index.php?do=predmet&kod={}"
HLAVICKA = ["kod", "anotace", "sylabus", "podminky", "literatura"]
VRSTVY = ("A", "B", "C")


def stahni(kod, obnovit=False):
    path = os.path.join(CACHE, f"{kod}.html")
    if obnovit or not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        req = urllib.request.Request(URL.format(kod), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read().decode("utf-8", "replace")
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
    return open(path, encoding="utf-8").read()


def ocisti(kus, oddelovac=" "):
    """Prevede kus HTML na cisty text; blokove predely nahradi oddelovacem."""
    kus = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", kus, flags=re.S | re.I)
    kus = re.sub(r"<\s*(br|/p|/li|/div|/tr|/h\d)\s*[^>]*>", "\x00", kus, flags=re.I)
    kus = re.sub(r"<[^>]*>", " ", kus)
    kus = htmlmod.unescape(kus)
    kusy = [re.sub(r"\s+", " ", c).strip(" \t ·-") for c in kus.split("\x00")]
    kusy = [c for c in kusy if c]
    return re.sub(r"\s+", " ", oddelovac.join(kusy)).strip()


def sekce(html, klic, oddelovac=" "):
    """Ceska varianta sekce <div id="pamela_<klic>_CZE">, bez 'Posledni uprava'."""
    m = re.search(r'<div id="pamela_%s_CZE"[^>]*>' % re.escape(klic), html)
    if not m:
        return ""
    zbytek = html[m.end():]
    # sekce konci sedivym odstavcem s datem posledni upravy
    konec = re.search(r'<div style="position:relative"', zbytek)
    if konec:
        zbytek = zbytek[:konec.start()]
    else:
        zbytek = zbytek.split('<div id="pamela_')[0]
    return ocisti(zbytek, oddelovac)


def parsuj(kod, obnovit=False):
    h = stahni(kod, obnovit)
    anotace = sekce(h, "A")
    cil = sekce(h, "C")
    # "Cil predmetu" je casto samostatna veta navic k anotaci; slucujeme
    if cil and cil.lower() not in anotace.lower():
        anotace = (anotace + " " + cil).strip()
    return {
        "kod": kod,
        "anotace": anotace,
        "sylabus": sekce(h, "S", " · "),
        "podminky": sekce(h, "E"),
        "literatura": sekce(h, "L", " · "),
    }


def kandidati():
    src = os.path.join(D, "predmety.csv")
    return [r["kod"] for r in csv.DictReader(open(src, encoding="utf-8"))
            if r["vrstva"] in VRSTVY]


def main():
    ap = argparse.ArgumentParser(description="Popisne sekce predmetu ze SIS")
    ap.add_argument("kody", nargs="*", help="jen vybrane kody - vypise na obrazovku")
    ap.add_argument("--obnovit", action="store_true", help="znovu stahnout HTML")
    ap.add_argument("--nahled", type=int, default=300, help="delka vypisu pole")
    a = ap.parse_args()

    if a.kody:
        for kod in a.kody:
            r = parsuj(kod, a.obnovit)
            for k in HLAVICKA:
                print(f"{k:11} {r[k][:a.nahled]}")
            print("-" * 70)
        return

    kody = kandidati()
    out = os.path.join(D, "anotace.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, HLAVICKA)
        w.writeheader()
        chybi = []
        for kod in kody:
            r = parsuj(kod, a.obnovit)
            w.writerow(r)
            if not r["anotace"] or not r["sylabus"]:
                chybi.append(kod)
            print(".", end="", flush=True)
    print(f"\n{len(kody)} predmetu -> {out}")
    if chybi:
        print("bez anotace nebo sylabu: " + ", ".join(chybi))


if __name__ == "__main__":
    main()
