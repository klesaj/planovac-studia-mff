#!/usr/bin/env python3
"""Kdo predmet ucil a ve kterych letech — historie vyucujicich z ankety.

Kdo uci v aktualnim ZS, rika data/ucitele.csv (rozvrh 2026/27). To se ale rok od roku
meni, takze pro planovani je potreba i historie: kdo se u predmetu toci, kdo je stalice
a kdo ucil naposledy pred peti lety. Ta informace je v obdobich anketnich zaznamu.

Vstup:  data/anketa_cisla.csv (obdobi = doklad, ze v tom semestru ucil),
        data/anketa_komentare.csv (slabsi doklad — datum pripominky),
        data/ucitele.csv (kdo uci v ZS 2026/27)
Vystup: data/ucitele_historie.csv
        kod, vyucujici, role, uci_v_zs, obdobi_pocet, prvni_rok, posledni_rok,
        roky (kompaktne, napr. "2019Z|2021Z|2024L"), obdobi (plne, pipe),
        odpovedi, prumer_vyucujici, prumer_predmet, komentaru, zdroj

Radek s prazdnym `vyucujici` = pripominky vedene k predmetu jako celku, ne k cloveku.
"""
import csv, os, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
HL = ["kod", "vyucujici", "role", "uci_v_zs", "obdobi_pocet", "prvni_rok", "posledni_rok",
      "roky", "obdobi", "odpovedi", "prumer_vyucujici", "prumer_predmet",
      "komentaru", "zdroj"]


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


def kompakt(obdobi):
    """'2019 / zimní' -> '2019Z'  (rok = rok zacatku akademickeho roku)"""
    r = rok(obdobi)
    return f"{r}{'L' if 'letní' in obdobi else 'Z'}" if r else ""


def rok_komentare(datum):
    """Datum pripominky -> akademicky rok. Anketa k ZS bezi v lednu az brezu."""
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", datum or "")
    if not m:
        return 0
    mesic, r = int(m.group(2)), int(m.group(3))
    return r - 1 if mesic <= 8 else r      # leden 2025 = akademicky rok 2024/25


def cislo(s):
    return float(s.replace(",", ".")) if s else None


def prumer(h):
    h = [x for x in h if x is not None]
    return f"{sum(h) / len(h):.2f}".replace(".", ",") if h else ""


def main():
    zs = defaultdict(set)                     # kod -> {klic jmena: role}
    jmena_zs = {}
    for u in nacti("ucitele.csv"):
        zs[u["kod"]].add((klic(u["ucitel"]), u["role"]))
        jmena_zs[(u["kod"], klic(u["ucitel"]))] = u["ucitel"]

    zaz = defaultdict(lambda: {"obdobi": {}, "kom": [], "jmeno": ""})
    for c in nacti("anketa_cisla.csv"):
        z = zaz[(c["kod"], klic(c["vyucujici"]), c["role"])]
        z["jmeno"] = z["jmeno"] or c["vyucujici"]
        z["obdobi"][c["obdobi"]] = c
    for k in nacti("anketa_komentare.csv"):
        z = zaz[(k["kod"], klic(k["vyucujici"]), k["role"])]
        z["jmeno"] = z["jmeno"] or k["vyucujici"]
        z["kom"].append(k)

    out = []
    for (kod, kl, role), z in zaz.items():
        radky = list(z["obdobi"].values())
        obd = sorted(z["obdobi"], key=rok)
        roky = [rok(o) for o in obd]
        zdroj = "anketa_cisla"
        if not obd:                            # jen pripominky: rok odhadni z jejich data
            roky = sorted({rok_komentare(k["datum"]) for k in z["kom"]} - {0})
            zdroj = "komentare"
        out.append({
            "kod": kod, "vyucujici": z["jmeno"], "role": role,
            "uci_v_zs": int((kl, role) in zs.get(kod, set())),
            "obdobi_pocet": len(obd), "prvni_rok": min(roky) if roky else "",
            "posledni_rok": max(roky) if roky else "",
            "roky": "|".join(kompakt(o) for o in obd) or "|".join(str(r) for r in roky),
            "obdobi": "|".join(obd),
            "odpovedi": sum(int(r["odpovedelo"] or 0) for r in radky),
            "prumer_vyucujici": prumer([cislo(r["celkove_vyucujici"])
                                        for r in sorted(radky, key=lambda r: -rok(r["obdobi"]))[:6]]),
            "prumer_predmet": prumer([cislo(r["celkove_predmet"])
                                      for r in sorted(radky, key=lambda r: -rok(r["obdobi"]))[:6]]),
            "komentaru": len(z["kom"]), "zdroj": zdroj})

    # ucitel z rozvrhu ZS, kterého anketa vubec nezna — at v tabulce nechybi
    zname = {(r["kod"], klic(r["vyucujici"]), r["role"]) for r in out}
    for kod, dvojice in zs.items():
        for kl, role in dvojice:
            if (kod, kl, role) not in zname:
                out.append({"kod": kod, "vyucujici": jmena_zs[(kod, kl)], "role": role,
                            "uci_v_zs": 1, "obdobi_pocet": 0, "prvni_rok": "",
                            "posledni_rok": "", "roky": "", "obdobi": "", "odpovedi": 0,
                            "prumer_vyucujici": "", "prumer_predmet": "", "komentaru": 0,
                            "zdroj": "rozvrh"})

    out.sort(key=lambda r: (r["kod"], -int(r["uci_v_zs"]),
                            -(int(r["posledni_rok"]) if r["posledni_rok"] else 0),
                            r["vyucujici"], r["role"]))
    with open(os.path.join(D, "ucitele_historie.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, HL)
        w.writeheader()
        w.writerows(out)
    lidi = len({(r["kod"], r["vyucujici"]) for r in out if r["vyucujici"]})
    print(f"-> data/ucitele_historie.csv ({len(out)} radku, {lidi} dvojic predmet+vyucujici, "
          f"{sum(1 for r in out if r['uci_v_zs'])} z toho uci v ZS 2026/27)")


if __name__ == "__main__":
    main()
