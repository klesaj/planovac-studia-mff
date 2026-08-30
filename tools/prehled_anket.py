#!/usr/bin/env python3
"""Cteci prehled ankety ke vsem sledovanym predmetum -> 12-ankety-prehled.md

Vypisuji se **vsichni** vyucujici, ktere anketa u predmetu zna, ne jen ti z rozvrhu
ZS 2026/27 — kdo predmet uci, se rok od roku meni a historie ("kdo se tam toci")
je pro planovani stejne dulezita jako aktualni obsazeni. U kazdeho je proto videt,
ktere roky ucil, a kdo uci ted, je oznaceny.

Vstup:  data/predmety.csv, data/sis.csv, data/ucitele.csv (kdo uci v ZS 2026/27),
        data/ucitele_historie.csv, data/rozvrh.csv,
        data/anketa_cisla.csv, data/anketa_komentare.csv
Vystup: 12-ankety-prehled.md k rucnimu overeni + data/anketa_souhrn.csv
        (souhrn zustava jen za dvojice z rozvrhu ZS — cte ho tools/prehled_rozvrhu.py)

Zamerne se nic neagreguje do plánu: overeny zaver zapisuje Jakub sam
do data/ankety.csv (kod, znamka, respondentu, shrnuti).
"""
import csv, os, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "12-ankety-prehled.md")
OD_ROKU = 2019          # starsi rocniky uz nevypovidaji o dnesni podobe vyuky
DNY = ["Po", "Út", "St", "Čt", "Pá"]


def nacti(j):
    p = os.path.join(D, j)
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


def klic(jmeno):
    """'Barták Roman' i 'prof. RNDr. Roman Barták, Ph.D.' -> {'barták','roman'}"""
    slova = re.split(r"[,\s]+", jmeno or "")
    return frozenset(w.lower() for w in slova if w and "." not in w and len(w) > 1)


def rok(obdobi):
    m = re.match(r"\s*(\d{4})", obdobi or "")
    return int(m.group(1)) if m else 0


def cislo(s):
    return float(s.replace(",", ".")) if s else None


def prumer(hodnoty):
    h = [x for x in hodnoty if x is not None]
    return f"{sum(h)/len(h):.2f}".replace(".", ",") if h else "—"


def roky_vetou(h):
    """'2019Z|2021Z|2024Z' -> '2019, 2021, 2024 (zimní)' — at je videt frekvence."""
    kusy = [k for k in (h.get("roky") or "").split("|") if k]
    if not kusy:
        return "anketa k němu nemá žádné období"
    sem = {k[-1] for k in kusy if k[-1] in "ZL"}
    znacka = {"Z": " (zimní)", "L": " (letní)"}.get(next(iter(sem))) if len(sem) == 1 else ""
    roky = ", ".join(k.rstrip("ZL") for k in kusy)
    ocas = "" if h.get("zdroj") == "anketa_cisla" else " — odhad z dat připomínek"
    return f"{roky}{znacka or ''}{ocas}"


def main():
    sis = {r["kod"]: r for r in nacti("sis.csv")}
    vyber = {r["kod"]: r for r in nacti("predmety.csv")}
    uc_zs = nacti("ucitele.csv")
    bloky = nacti("rozvrh.csv")
    cisla = [r for r in nacti("anketa_cisla.csv") if rok(r["obdobi"]) >= OD_ROKU]
    komentare = nacti("anketa_komentare.csv")
    historie = nacti("ucitele_historie.csv")

    zs = defaultdict(dict)          # kod -> {klic jmena: {...}}  kdo uci v ZS 2026/27
    for u in uc_zs:
        z = zs[u["kod"]].setdefault(klic(u["ucitel"]),
                                    {"jmeno": u["ucitel"], "role": set(), "paralelek": 0})
        z["role"].add(u["role"])
        z["paralelek"] += int(u["paralelek"])

    bloky_uc = defaultdict(list)
    for b in bloky:
        bloky_uc[(b["kod"], klic(b["ucitel"]))].append(b)

    cisla_uc, kom_uc = defaultdict(list), defaultdict(list)
    for r in cisla:
        cisla_uc[(r["kod"], klic(r["vyucujici"]), r["role"])].append(r)
    for r in komentare:
        kom_uc[(r["kod"], klic(r["vyucujici"]), r["role"])].append(r)

    hist = defaultdict(list)
    for h in historie:
        hist[h["kod"]].append(h)

    L = ["# Ankety ke sledovaným předmětům",
         "",
         "> Stahuje `tools/anketa.py` z veřejných výsledků ankety SIS, historii "
         "vyučujících počítá `tools/ucitele_historie.py`, páruje `tools/prehled_anket.py`.",
         f"> Číselné hodnocení od {OD_ROKU}/20 dál, komentáře všechny, co SIS vydá. "
         "**Škála 1 = nejlepší, 4 = nejhorší.**",
         "> Vypsaní jsou **všichni vyučující, které anketa u předmětu zná** — kdo učí "
         "v ZS 2026/27, je označený **(učí teď)**. U každého jsou roky, ve kterých "
         "předmět učil, aby bylo vidět, kdo je stálice a kdo se tam jen mihl.",
         "",
         "**K ověření:** sedí komentář na toho vyučujícího a tu roli (přednáška × "
         "cvičení), pod kterou visí? Anketa u garanta ukazuje i připomínky k ostatním "
         "vyučujícím předmětu, takže tady může být přiřazení posunuté. Ověřený závěr "
         "patří do `data/ankety.csv`.",
         ""]

    for kod in [k for k in vyber if hist.get(k)]:
        nazev = sis.get(kod, {}).get("nazev", "")
        vrstva = vyber[kod]["vrstva"]
        L += [f"## {kod} — {nazev}",
              f"*vrstva {vrstva} · {sis.get(kod, {}).get('kredity','?')} kr · "
              f"{sis.get(kod, {}).get('rozsah','')} {sis.get(kod, {}).get('examinace','')}*",
              ""]
        radky_h = sorted(hist[kod],
                         key=lambda h: (-int(h["uci_v_zs"]),
                                        -(int(h["posledni_rok"]) if h["posledni_rok"] else 0),
                                        h["vyucujici"], h["role"]))
        L += ["| Vyučující | Role | Učil v letech | Období | Odpovědí | Připomínek |",
              "|---|---|---|---:|---:|---:|"]
        for h in radky_h:
            jm = h["vyucujici"] or "*(připomínky k předmětu)*"
            znak = " **(učí teď)**" if h["uci_v_zs"] == "1" else ""
            L.append(f"| {jm}{znak} | {h['role']} | {roky_vetou(h)} | "
                     f"{h['obdobi_pocet']} | {h['odpovedi']} | {h['komentaru']} |")
        L.append("")

        for h in radky_h:
            k_jm, role = klic(h["vyucujici"]), h["role"]
            jm = h["vyucujici"] or "Připomínky k předmětu jako celku"
            znak = " — **učí v ZS 2026/27**" if h["uci_v_zs"] == "1" else ""
            L += [f"### {jm} — {role}{znak}", "",
                  f"**Učil v letech:** {roky_vetou(h)}", ""]
            if h["uci_v_zs"] == "1":
                bl = sorted(bloky_uc[(kod, k_jm)],
                            key=lambda b: (DNY.index(b["den"]) if b["den"] in DNY else 9,
                                           b["od"]))
                kdy = "; ".join(f'{b["den"]} {b["od"]}–{b["do"]} {b["mistnost"]} '
                                f'({b["typ"]}{", " + b["poznamka"] if b["poznamka"] else ""})'
                                for b in bl)
                L += [f"**V rozvrhu ZS 2026/27:** {kdy or '—'}", ""]

            c = sorted(cisla_uc[(kod, k_jm, role)], key=lambda r: -rok(r["obdobi"]))
            if c:
                p_predmet = prumer([cislo(r["celkove_predmet"]) for r in c[:6]])
                odpovedi = sum(int(r["odpovedelo"] or 0) for r in c[:6])
                L += [f"Číselně (posledních {min(len(c),6)} záznamů od {OD_ROKU}): "
                      f"celkové hodnocení **{p_predmet}**, dohromady {odpovedi} odpovědí.", "",
                      "| Období | Role | Odpovědělo | Celkové | Srozum. | Obtížnost |",
                      "|---|---|---:|---:|---:|---:|"]
                for r in c[:8]:
                    L.append(f"| {r['obdobi']} | {r['role']} | {r['odpovedelo']}/{r['zapsano']} "
                             f"| {r['celkove_predmet'] or '—'} | {r['srozumitelnost'] or '—'} "
                             f"| {r['obtiznost'] or '—'} |")
                L.append("")
            else:
                L += [f"*Číselné hodnocení k téhle dvojici SIS od {OD_ROKU} nemá.*", ""]

            km = sorted(kom_uc[(kod, k_jm, role)],
                        key=lambda r: r["datum"][-4:] + r["datum"][3:5], reverse=True)
            if km:
                L += [f"**Připomínky ({len(km)}):**", ""]
                for r in km:
                    L.append(f"- *{r['datum']}, {r['rocnik']}, {r['program']}, {r['role']}* — "
                             f"{r['text']}")
                L.append("")
            else:
                L += ["*Žádné připomínky.*", ""]

    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    # souhrn drzi jen dvojice z rozvrhu ZS — cte ho tools/prehled_rozvrhu.py.
    # Pocita se pres vsechny role toho cloveka dohromady, jako predtim.
    slouceny = {}
    for kod, lide in zs.items():
        for k_jm, info in lide.items():
            c = sorted([r for role in info["role"] for r in cisla_uc[(kod, k_jm, role)]],
                       key=lambda r: -rok(r["obdobi"]))
            if not c:
                continue
            slouceny[(kod, info["jmeno"])] = {
                "kod": kod, "ucitel": info["jmeno"],
                "role": ", ".join(sorted(info["role"])), "zaznamu": len(c),
                "odpovedi": sum(int(r["odpovedelo"] or 0) for r in c[:6]),
                "celkove_prumer": prumer([cislo(r["celkove_predmet"]) for r in c[:6]]),
                "komentaru": sum(len(kom_uc[(kod, k_jm, role)]) for role in info["role"])}
    with open(os.path.join(D, "anketa_souhrn.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["kod", "ucitel", "role", "zaznamu", "odpovedi",
                               "celkove_prumer", "komentaru"])
        w.writeheader()
        w.writerows(slouceny.values())
    print(f"-> {OUT} ({sum(1 for h in historie)} dvojic vyucujici+role), "
          f"data/anketa_souhrn.csv ({len(slouceny)} dvojic z rozvrhu ZS)")


if __name__ == "__main__":
    main()
