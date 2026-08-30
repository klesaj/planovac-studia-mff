#!/usr/bin/env python3
"""Stahne rozvrhy predmetu ze SIS a normalizuje je do data/rozvrh.csv.

SIS ma u kazdeho predmetu verejny CSV export rozvrhu (bez prihlaseni):
    rozvrhng/roz_predmet_macro.php?fak=11320&skr=<rok>&sem=<1|2>&predmet=<KOD>&csv=1
Kodovani cp1250, oddelovac ';', cas v minutach od pulnoci.

Bere se JEN zimni semestr aktualniho planovaneho roku (ZS 2026/27). Rozvrh je
v teto fazi predbezny - SIS ho ma "v pusobnosti rozvrhove komise" a muze se menit.
Predmety, ktere se v ZS neuci nebo nemaji rozvrhovanou vyuku, proste nevrati nic;
nic se za ne nedoplnuje z jinych rocniku.

Pouziti:
    python3 tools/rozvrh.py                # vsechny kandidaty z data/predmety.csv
    python3 tools/rozvrh.py --sem 2        # letni semestr (az ho SIS vypise)
    python3 tools/rozvrh.py NAIL069        # jen vybrane kody, vypise na obrazovku
"""
import argparse, csv, io, os, re, sys, urllib.request
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "zdroje", "rozvrhy")
URL = ("https://is.cuni.cz/studium/rozvrhng/roz_predmet_macro.php"
       "?fak=11320&skr={skr}&sem={sem}&predmet={kod}{ustav}&csv=1")
DNY = {"1": "Po", "2": "Út", "3": "St", "4": "Čt", "5": "Pá", "6": "So", "7": "Ne"}
TYPY = {"p": "přednáška", "x": "cvičení", "s": "seminář", "c": "cvičení"}
ZS, LS = "1", "2"
HLAVICKA = ["kod", "typ", "paralelka", "den", "od", "do", "mistnost", "ucitel",
            "vybrano", "poznamka", "skr", "sem"]


def cas(minuty):
    m = int(minuty)
    return f"{m // 60}:{m % 60:02d}"


def stahni(kod, skr, sem, ustav="", obnovit=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{skr}-{sem}-{kod}.csv")
    if obnovit or not os.path.exists(path):
        url = URL.format(skr=skr, sem=sem, kod=kod,
                         ustav=f"&ustav={ustav}" if ustav else "")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
    return open(path, "rb").read().decode("cp1250", "replace")


def parsuj(kod, text, skr, sem):
    # kdyz predmet v danem semestru neexistuje, SIS vrati misto CSV celou HTML stranku
    if not text.startswith("id listku"):
        return []
    radky = list(csv.reader(io.StringIO(text), delimiter=";"))
    if len(radky) < 2:
        return []
    out = []
    for r in radky[1:]:
        if len(r) < 13 or not r[4] or not r[5]:
            continue
        listek = r[0]
        typ_kod = (re.search(re.escape(kod) + r"([a-zA-Z])", listek) or [None, "?"])[1].lower()
        pozn = []
        if r[11]:
            pozn.append({"liche": "liché týdny", "sude": "sudé týdny"}.get(r[11], r[11]))
        if r[10] and r[10] != "13":
            pozn.append(f"{r[10]} týdnů")
        out.append({
            "kod": kod,
            "typ": TYPY.get(typ_kod, typ_kod),
            "paralelka": listek,
            "den": DNY.get(r[4], r[4]),
            "od": cas(r[5]),
            "do": cas(int(r[5]) + int(r[7] or 0)),
            "mistnost": r[6],
            "ucitel": re.sub(r",.*", "", r[12]) if r[12] else "",
            "vybrano": "",
            "poznamka": ", ".join(pozn),
            "skr": skr, "sem": sem,
        })
    return out


def oznac_vyber(bloky):
    """Prednasky a jedine mozne cviceni jsou dane; kde je vic paralelek, vybira Jakub."""
    podle_typu = defaultdict(set)
    for b in bloky:
        podle_typu[(b["kod"], b["typ"])].add(b["paralelka"])
    for b in bloky:
        jedina = len(podle_typu[(b["kod"], b["typ"])]) == 1
        b["vybrano"] = "1" if (b["typ"] == "přednáška" or jedina) else ""
    return bloky


def ucitele(bloky):
    """Kdo v tomhle semestru realne uci - podklad pro filtrovani anket."""
    souhrn = defaultdict(lambda: {"paralelky": set(), "bloku": 0})
    for b in bloky:
        z = souhrn[(b["kod"], b["ucitel"], b["typ"])]
        z["paralelky"].add(b["paralelka"])
        z["bloku"] += 1
    return [{"kod": k, "ucitel": u, "role": t,
             "paralelek": len(v["paralelky"]), "bloku": v["bloku"]}
            for (k, u, t), v in sorted(souhrn.items())]


def ustav_z_sis():
    p = os.path.join(D, "sis.csv")
    out = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            m = re.search(r"\((32-[A-Z]+)\)", r.get("pracoviste", ""))
            if m:
                out[r["kod"]] = m.group(1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kody", nargs="*")
    ap.add_argument("--skr", default="2026", help="akademicky rok, napr. 2026 = 2026/27")
    ap.add_argument("--sem", default=ZS, choices=[ZS, LS], help="1 = zimni, 2 = letni")
    ap.add_argument("--obnovit", action="store_true", help="ignoruj cache")
    a = ap.parse_args()

    ustavy = ustav_z_sis()
    if a.kody:
        for kod in a.kody:
            for sem in (ZS, LS):
                for b in parsuj(kod, stahni(kod, a.skr, sem, ustavy.get(kod, ""), a.obnovit), a.skr, sem):
                    print(" ".join(f"{b[k]}" for k in
                                   ("kod", "typ", "paralelka", "den", "od", "do", "mistnost", "ucitel")))
        return

    vyber = list(csv.DictReader(open(os.path.join(D, "predmety.csv"), encoding="utf-8")))
    bloky, prazdne = [], []
    for r in vyber:
        if r["vrstva"] not in "ABC":        # vrstva X = zamitnute, ty nezajimaji
            continue
        nove = parsuj(r["kod"], stahni(r["kod"], a.skr, a.sem, ustavy.get(r["kod"], ""),
                                       a.obnovit), a.skr, a.sem)
        (bloky.extend(nove) if nove else prazdne.append(r["kod"]))
        print(".", end="", flush=True)
    oznac_vyber(bloky)
    out = os.path.join(D, "rozvrh.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, HLAVICKA)
        w.writeheader()
        w.writerows(sorted(bloky, key=lambda b: (b["kod"], b["paralelka"], b["den"])))
    out2 = os.path.join(D, "ucitele.csv")
    with open(out2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["kod", "ucitel", "role", "paralelek", "bloku"])
        w.writeheader()
        w.writerows(ucitele(bloky))
    print(f"\n{len(bloky)} bloku -> {out}")
    print(f"{len(ucitele(bloky))} dvojic ucitel+role -> {out2}")
    if prazdne:
        print("bez rozvrhovane vyuky v tomhle semestru: " + ", ".join(prazdne))


if __name__ == "__main__":
    main()
