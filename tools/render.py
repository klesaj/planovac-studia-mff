#!/usr/bin/env python3
"""Slozi z data/*.csv citelnou tabulku predmetu -> 10-predmety-tabulka.md

Vstupy (vsechny v data/):
    predmety.csv  - rucne udrzovany vyber: vrstva, skupina, szz, plan_semestr, stav, poznamka
    sis.csv       - automaticky z tools/sis.py (nazev, kredity, rozsah, vyucujici, ...)
    ankety.csv    - VOLITELNE: kod,znamka,respondentu,shrnuti      (z anket v SIS)
    rozvrh.csv    - VOLITELNE: kod,typ,den,od,do,mistnost,ucitel   (z CSV rozvrhu v SIS)

Spusteni:  python3 tools/render.py
"""
import csv, os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
SEMESTRY = ["ZS1", "LS1", "ZS2", "LS2", "ZS3", "LS3"]
POPIS = {"ZS1": "ZS 2026/27", "LS1": "LS 2027", "ZS2": "ZS 2027/28",
         "LS2": "LS 2028", "ZS3": "ZS 2028/29", "LS3": "LS 2029"}
SKUPINY = ["povinny", "profilujici", "rozsirujici", "volitelny"]
import program as _cfg
MINIMA = _cfg.minima({"povinny": 47, "profilujici": 38,
                      "rozsirujici": 15, "volitelny": 0})


def nacti(jmeno, klic="kod"):
    p = os.path.join(D, jmeno)
    if not os.path.exists(p):
        return {}
    return {r[klic]: r for r in csv.DictReader(open(p, encoding="utf-8"))}


def nacti_vic(jmeno):
    p = os.path.join(D, jmeno)
    out = defaultdict(list)
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            out[r["kod"]].append(r)
    return out


def zkrat(jmena, n=2):
    """'prof. RNDr. Roman Bartak, Ph.D. RNDr. Jiri Fink, Ph.D.' -> 'Bartak, Fink'"""
    if not jmena:
        return ""
    kusy, slova = [], jmena.replace(",", " ,").split()
    prijmeni = []
    for i, w in enumerate(slova):
        if w == ",":
            if prijmeni:
                kusy.append(prijmeni[-1])
            prijmeni = []
        elif w[0:1].isupper() and "." not in w:
            prijmeni.append(w)
    if prijmeni:
        kusy.append(prijmeni[-1])
    videno = [k for i, k in enumerate(kusy) if k not in kusy[:i]]
    return ", ".join(videno[:n]) + (" ad." if len(videno) > n else "")


def main():
    vyber = list(csv.DictReader(open(os.path.join(D, "predmety.csv"), encoding="utf-8")))
    sis, ankety = nacti("sis.csv"), nacti("ankety.csv")
    rozvrh = nacti_vic("rozvrh.csv")
    for r in vyber:
        r.update({k: v for k, v in sis.get(r["kod"], {}).items() if k != "kod"})
        r["anketa"] = ankety.get(r["kod"], {})
        r["bloky"] = rozvrh.get(r["kod"], [])
        r["kr"] = int(r.get("kredity") or 0)
        if not r.get("vyucujici"):          # u nekterych predmetu SIS uvadi jen garanta
            r["vyucujici"] = r.get("garant", "")

    L = ["# Předměty: přehledová tabulka",
         "",
         "> Generováno `tools/render.py` z `data/predmety.csv` + `data/sis.csv`.",
         "> **Needituj ručně** — uprav CSV a spusť skript znovu.",
         "> Zdroj věcných dat: SIS, AR 2025/2026. Plán 2026/2027 zatím nevyšel.",
         ""]

    # --- souhrn kreditu ---
    L += ["## Kreditová bilance (vrstvy A + B)", "",
          "| Skupina | Kredity | Minimum | Rezerva |", "|---|---:|---:|---:|"]
    celkem = 0
    for s in SKUPINY:
        kr = sum(r["kr"] for r in vyber if r["vrstva"] in "AB" and r["skupina"] == s)
        celkem += kr
        L.append(f"| {s} | {kr} | {MINIMA[s]} | {kr - MINIMA[s]:+d} |")
    L += [f"| **celkem** | **{celkem}** | **120** | **{celkem - 120:+d}** |",
          "", "Plus 6 kr uznání z Bc. (NAIL125 + NJAZ202), pokud garant schválí.", ""]

    # --- plan po semestrech ---
    L += ["## Plán po semestrech", ""]
    kumul = 0
    for sem in SEMESTRY:
        v = [r for r in vyber if r["plan_semestr"] == sem]
        if not v:
            continue
        kr = sum(r["kr"] for r in v)
        kumul += kr
        hod = sum(sum(int(x) for x in (r.get("rozsah") or "0/0").split("/")) for r in v)
        L += [f"### {POPIS[sem]} — {kr} kr, {hod} h/týden kontaktní výuky "
              f"(kumulativně {kumul} kr)", "",
              "| Kód | Předmět | Kr | Rozsah | Zk | Skupina | SZZ | Vyučující |",
              "|---|---|---:|---|---|---|---|---|"]
        for r in sorted(v, key=lambda r: -r["kr"]):
            szz = r["szz"] if r["szz"] != "-" else ""
            L.append(f"| `{r['kod']}` | {r.get('nazev','')} | {r['kr']} | {r.get('rozsah','')} "
                     f"| {r.get('examinace','')} | {r['skupina']} | {szz} | {zkrat(r.get('vyucujici',''))} |")
        L.append("")

    # --- vrstva C a vyrazene ---
    for vrstva, nadpis in [("C", "Rezerva (vrstva C) — bereš, jen když zbude kapacita"),
                           ("X", "Vyřazeno")]:
        v = [r for r in vyber if r["vrstva"] == vrstva]
        if not v:
            continue
        L += [f"## {nadpis}", "",
              "| Kód | Předmět | Kr | Sem | Skupina | Stav | Poznámka |",
              "|---|---|---:|---|---|---|---|"]
        for r in v:
            L.append(f"| `{r['kod']}` | {r.get('nazev','')} | {r['kr']} | {r.get('semestr','')} "
                     f"| {r['skupina']} | {r['stav']} | {r['poznamka']} |")
        L.append("")

    # --- detaily ---
    L += ["## Detaily předmětů (vrstvy A + B)", ""]
    for r in [x for x in vyber if x["vrstva"] in "AB"]:
        L += [f"### `{r['kod']}` {r.get('nazev','')}", "",
              f"*{r.get('anglicky','')}* · {r.get('pracoviste','')}", "",
              f"- **{r['kr']} kr** · {r.get('semestr','')} semestr · {r.get('rozsah','')} "
              f"{r.get('examinace','')} · {r.get('forma','')}",
              f"- Skupina: **{r['skupina']}**" +
              (f" · SZZ okruh: **{r['szz']}**" if r["szz"] != "-" else "") +
              f" · plán: **{POPIS.get(r['plan_semestr'], r['plan_semestr'])}**",
              f"- Vyučující: {r.get('vyucujici','') or '—'}",
              f"- Garant: {r.get('garant','') or '—'}"]
        if r.get("neslucitelnost"):
            L.append(f"- Neslučitelnost: `{r['neslucitelnost']}`")
        if r["poznamka"]:
            L.append(f"- {r['poznamka']}")
        if r["stav"] != "plánováno":
            L.append(f"- **Stav: {r['stav']}**")
        if r["anketa"]:
            a = r["anketa"]
            L.append(f"- Anketa: **{a.get('znamka','?')}** ({a.get('respondentu','?')} resp.) "
                     f"{a.get('shrnuti','')}")
        for b in r["bloky"]:
            L.append(f"- Rozvrh: {b.get('typ','')} {b.get('den','')} {b.get('od','')}–{b.get('do','')} "
                     f"{b.get('mistnost','')} {b.get('ucitel','')}")
        L.append("")

    out = os.path.join(ROOT, "10-predmety-tabulka.md")
    open(out, "w", encoding="utf-8").write("\n".join(L))
    print(f"-> {out} ({len(vyber)} predmetu, {celkem} kr v A+B)")


if __name__ == "__main__":
    main()
