#!/usr/bin/env python3
"""Cteci prehled rozvrhu ZS ze SIS -> 11-rozvrh-ZS.md

Nic nevybira ani neplanuje: ukazuje vsechny paralelky, ktere SIS na ZS 2026/27 vypsal,
aby se z nich dalo skladat. Vyber paralelky se zapisuje do sloupce `vybrano`
v data/rozvrh.csv (1 = beru).
"""
import csv, os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "11-rozvrh-ZS.md")
DNY = ["Po", "Út", "St", "Čt", "Pá"]


def nacti(j):
    p = os.path.join(D, j)
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


def min_(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def main():
    bloky = nacti("rozvrh.csv")
    sis = {r["kod"]: r for r in nacti("sis.csv")}
    pred = {r["kod"]: r for r in nacti("predmety.csv")}
    souhrn = {(r["kod"], r["ucitel"]): r for r in nacti("anketa_souhrn.csv")}
    if not bloky:
        print("data/rozvrh.csv je prazdny — spust nejdriv tools/rozvrh.py")
        return
    rok = bloky[0]["skr"]
    L = [f"# Rozvrh ZS {rok}/{int(rok) % 100 + 1} — co SIS vypsal", "",
         "> Staženo `tools/rozvrh.py` z veřejného CSV exportu rozvrhu SIS "
         "(`rozvrhng/roz_predmet_macro.php?...&csv=1`).",
         "> Rozvrh je **předběžný** — SIS ho vede jako „v působnosti rozvrhové komise\".",
         "> Hodnocení v závorce je průměr z ankety (1 = nejlepší), detail v "
         "`12-ankety-prehled.md`.", "",
         "## Přehled dne po dni", ""]

    # --- mrizka po dnech ---
    po_dnech = defaultdict(list)
    for b in bloky:
        po_dnech[b["den"]].append(b)
    for den in DNY:
        if den not in po_dnech:
            continue
        L += [f"### {den}", "",
              "| Čas | Kód | Předmět | Typ | Paralelka | Místnost | Vyučující | Pozn. |",
              "|---|---|---|---|---|---|---|---|"]
        for b in sorted(po_dnech[den], key=lambda x: min_(x["od"])):
            L.append(f"| {b['od']}–{b['do']} | `{b['kod']}` "
                     f"| {sis.get(b['kod'], {}).get('nazev', '')} | {b['typ']} "
                     f"| `{b['paralelka']}` | {b['mistnost']} | {b['ucitel']} "
                     f"| {b['poznamka']} |")
        L.append("")

    # --- po predmetech ---
    L += ["## Po předmětech", ""]
    podle_kodu = defaultdict(list)
    for b in bloky:
        podle_kodu[b["kod"]].append(b)
    for kod in sorted(podle_kodu, key=lambda k: (pred.get(k, {}).get("vrstva", "Z"), k)):
        s = sis.get(kod, {})
        p = pred.get(kod, {})
        L += [f"### `{kod}` {s.get('nazev','')} — {s.get('kredity','?')} kr, "
              f"{s.get('rozsah','')} {s.get('examinace','')}",
              "",
              f"vrstva {p.get('vrstva','?')} · {p.get('skupina','?')}"
              + (f" · SZZ {p['szz']}" if p.get("szz", "-") != "-" else "")
              + (f" · {p['poznamka']}" if p.get("poznamka") else ""), ""]
        for typ in ("přednáška", "cvičení", "seminář"):
            skup = defaultdict(list)
            for b in podle_kodu[kod]:
                if b["typ"] == typ:
                    skup[b["paralelka"]].append(b)
            if not skup:
                continue
            L.append(f"**{typ.capitalize()}** — {len(skup)} "
                     f"{'možnost' if len(skup) == 1 else 'paralelek na výběr'}:")
            L.append("")
            for par, bs in sorted(skup.items()):
                kdy = "; ".join(f"{b['den']} {b['od']}–{b['do']} {b['mistnost']}"
                                + (f" ({b['poznamka']})" if b["poznamka"] else "")
                                for b in sorted(bs, key=lambda x: (DNY.index(x["den"]) if x["den"] in DNY else 9, min_(x["od"]))))
                ucitel = bs[0]["ucitel"]
                a = souhrn.get((kod, ucitel))
                znamka = f" — anketa {a['celkove_prumer']} z {a['odpovedi']} odpovědí" if a else ""
                vybrano = " ✅" if bs[0].get("vybrano") == "1" else ""
                L.append(f"- `{par}` {kdy} · **{ucitel}**{znamka}{vybrano}")
            L.append("")

    chybi = [k for k, v in pred.items()
             if v["vrstva"] in "ABC" and sis.get(k, {}).get("semestr") in ("zimní", "oba")
             and k not in podle_kodu]
    if chybi:
        L += ["## Zimní předměty bez rozvrhované výuky", "",
              "SIS je pro ZS vypsal jako předmět, ale žádný rozvrhový lístek nemají "
              "(diplomka, projekt, výuka po domluvě — nebo se prostě letos neotevírají):", ""]
        for k in chybi:
            L.append(f"- `{k}` {sis.get(k, {}).get('nazev','')} — stav v SIS: "
                     f"**{sis.get(k, {}).get('stav','?')}**")
        L.append("")
    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print(f"-> {OUT} ({len(bloky)} bloku, {len(podle_kodu)} predmetu)")


if __name__ == "__main__":
    main()
