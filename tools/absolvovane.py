#!/usr/bin/env python3
"""Nacte vypis vysledku ze SIS do data/absolvovane.csv.

Vypis se stahuje v SIS: Vysledky zkousek - prohlizeni -> Studijni mezivysledky
-> tisk. Vznikne PDF; da se predat rovnou, nebo uz prevedene pdftotext -layout.

Pouziti:
    python3 tools/absolvovane.py vypis.pdf        # -> data/absolvovane.csv
    python3 tools/absolvovane.py vypis.txt
    python3 tools/absolvovane.py --kontrola       # porovna s planem, nic nezapisuje

Kontrola hlasi:
  * predmety z planu neslucitelne s necim, co uz mam splnene,
  * predmety z planu, ktere uz mam splnene,
  * predmety zapsane a nesplnene (ty jde zapsat znovu),
  * bilanci kreditu podle typu v bakalari (podklad pro zadost o uznani).
"""
import csv, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "absolvovane.csv")
FIELDS = ["rok", "kod", "nazev", "examinace", "typ_v_bc", "kredity",
          "stav", "znamka", "datum", "poznamka"]

KOD = re.compile(r"^\s*(N[A-Z]{2,4}\d{3})\s+(.*)$")
ROK = re.compile(r"^\s*(\d{4}/\d{4})\s*$")
DATUM = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")
# konec radku: kredity a dvakrat Splneno/Nesplneno (za semestr a celkem)
OCAS = re.compile(r"\s(\d{1,2})\s+(Splněno|Nesplněno)\s+(Splněno|Nesplněno)\s*$")
TYP = re.compile(r"(povinně volitelný|povinný|volitelný)")
EXAM = re.compile(r"\b(Z\+Zk|KZ|Zk|Dipl|SZ|Z)\b")
# radky hlavicky a soucrove paty, ktere nepatri k predchozimu predmetu
PATA = re.compile(r"^(Získané|Studijní průměr|Výsledky|Jméno|Narozen|Z\s+L\s+Kód|"
                  r"Zimní semestr|sem\)|Uznané|Celkem|Celkový|Celkové)")


def text(cesta):
    if cesta.lower().endswith(".pdf"):
        return subprocess.run(["pdftotext", "-layout", cesta, "-"],
                              capture_output=True, text=True, check=True).stdout
    return open(cesta, encoding="utf-8").read()


def parsuj(cesta):
    """Radky s kodem jsou zaznamy; radky bez kodu patri predchozimu zaznamu
    (zalomeny nazev nebo druhy pokus u Z+Zk, kde se zvlast zapocet a zkouska)."""
    rok = ""
    zaznamy = []
    for radek in text(cesta).splitlines():
        m = ROK.match(radek)
        if m:
            rok = m.group(1)
            continue
        m = KOD.match(radek)
        if m:
            zaznamy.append({"rok": rok, "kod": m.group(1), "radky": [m.group(2)]})
        elif zaznamy and radek.strip() and not PATA.match(radek.strip()):
            zaznamy[-1]["radky"].append(radek)
    return [dorob(z) for z in zaznamy]


def dorob(z):
    cely = " ".join(z["radky"])
    prvni = z["radky"][0]

    ocas = OCAS.search(prvni)
    kredity = ocas.group(1) if ocas else ""
    stav = "splněno" if (ocas and ocas.group(3) == "Splněno") else "nesplněno"
    hlava = prvni[:ocas.start()] if ocas else prvni

    typ = TYP.search(hlava)
    exam = EXAM.search(hlava)
    # nazev konci tam, kde zacina typ examinace
    nazev = hlava[:exam.start()].strip() if exam else hlava.strip()
    # zalomeny nazev pokracuje na dalsich radcich pred prvnim datem
    for r in z["radky"][1:]:
        zbytek = r.strip()
        if zbytek and not DATUM.search(r) and not re.match(r"^\d", zbytek):
            nazev += " " + zbytek
    nazev = re.sub(r"\s{2,}", " ", nazev).strip()

    # znamka: posledni ciselny vysledek (1/2/3) u zkousky, Z u pouheho zapoctu
    znamky = re.findall(r"\s([1-4]|Z)\s+\d{2}\.\d{2}\.\d{4}", cely)
    znamka = ""
    for v in znamky:
        if v.isdigit():
            znamka = v
    if not znamka and znamky:
        znamka = "Z"
    data = DATUM.findall(cely)
    return {"rok": z["rok"], "kod": z["kod"], "nazev": nazev,
            "examinace": exam.group(1) if exam else "",
            "typ_v_bc": typ.group(1) if typ else "volitelný",
            "kredity": kredity, "stav": stav, "znamka": znamka,
            "datum": data[-1] if data else "", "poznamka": ""}


def nacti_csv(jmeno):
    p = os.path.join(ROOT, "data", jmeno)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def kontrola():
    abs_ = nacti_csv("absolvovane.csv")
    if not abs_:
        print("data/absolvovane.csv neexistuje nebo je prázdný.\n"
              "Stáhni si v SIS výpis (Výsledky zkoušek → Studijní mezivýsledky → tisk)\n"
              "a spusť: python3 tools/absolvovane.py <vypis.pdf>")
        return 1
    splneno = {r["kod"] for r in abs_ if r["stav"] == "splněno"}
    nesplneno = {r["kod"] for r in abs_ if r["stav"] != "splněno"}
    sis = {r["kod"]: r for r in nacti_csv("sis.csv")}
    plan = [r for r in nacti_csv("predmety.csv") if r["vrstva"] in "ABC"]

    print(f"Výpis: {len(abs_)} předmětů, {len(splneno)} splněno, "
          f"{len(nesplneno)} zapsáno a nesplněno.\n")

    kolize, uz_mam = [], []
    for r in plan:
        s = sis.get(r["kod"], {})
        strety = [k for k in re.findall(r"N[A-Z]{2,4}\d{3}", s.get("neslucitelnost", ""))
                  if k in splneno]
        if strety:
            kolize.append((r["kod"], s.get("nazev", ""), strety))
        if r["kod"] in splneno:
            uz_mam.append((r["kod"], s.get("nazev", "")))

    if kolize:
        print("NESLUČITELNÉ s tím, co už máš splněné — nezapsatelné:")
        for kod, nazev, s in kolize:
            print(f"  {kod} {nazev} × {', '.join(s)}")
    else:
        print("Neslučitelnost s bakalářem: nic v nabídce nekoliduje.")

    if uz_mam:
        print("\nUž máš splněné, přesto je to v nabídce:")
        for kod, nazev in uz_mam:
            print(f"  {kod} {nazev}")

    v_nabidce = {r["kod"] for r in plan}
    znovu = sorted(nesplneno & v_nabidce)
    if znovu:
        print("\nZapsané a nesplněné v bakaláři → jde zapsat znovu:")
        for kod in znovu:
            print(f"  {kod} {sis.get(kod, {}).get('nazev', '')}")

    print("\nKredity podle typu v bakaláři (podklad k žádosti o uznání):")
    soucty = {}
    for r in abs_:
        if r["stav"] == "splněno":
            soucty[r["typ_v_bc"]] = soucty.get(r["typ_v_bc"], 0) + int(r["kredity"] or 0)
    for typ, kr in sorted(soucty.items()):
        print(f"  {typ:20} {kr:3} kr")
    print(f"  {'celkem':20} {sum(soucty.values()):3} kr")
    print("\nUznat lze jen to, co přebylo nad kredity potřebné k dokončení bakaláře,\n"
          "a jen ve skupině, kde přebytek vznikl. Rozhoduje garant programu.")
    return 0


def main():
    if "--kontrola" in sys.argv:
        sys.exit(kontrola())
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    zaznamy = parsuj(sys.argv[1])
    if not zaznamy:
        print("Ve výpisu nejsou žádné předměty — je to opravdu studijní mezivýsledky ze SIS?")
        sys.exit(1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(zaznamy)
    kr = sum(int(z["kredity"] or 0) for z in zaznamy if z["stav"] == "splněno")
    print(f"{len(zaznamy)} předmětů, {kr} kreditů splněno -> {OUT}")
    print("Zkontroluj si to proti výpisu a pak spusť: python3 tools/absolvovane.py --kontrola")


if __name__ == "__main__":
    main()
