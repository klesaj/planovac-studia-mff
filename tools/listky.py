#!/usr/bin/env python3
"""Doplni k rozvrhovym listkum jazyk vyuky a kapacitu (CSV export SIS je nema).

CSV export rozvrhu (tools/rozvrh.py) obsahuje casy, ucebny a ucitele, ale ne
jazyk vyuky ani obsazenost. Ty jsou jen v HTML tabulce na tehle strance:
    rozvrhng/roz_predmet_macro.php?fak=11320&skr=<rok>&sem=<1|2>&predmet=<KOD>
Sloupce tabulky: kod listku | P/X | nazev | ucitele | cas | ucebna | delka |
jazyk | prihlaseno (kapacita) | studenti | skupiny.

Sloupec s poctem studentu vypada bud "82" (kapacita neomezena), nebo
"44 (50)" - prvni cislo je pocet zapsanych, cislo v zavorce kapacita.

Bere se JEN zimni semestr planovaneho roku (ZS 2026/27), stejne jako rozvrh.py.
Predmety, ktere v danem semestru rozvrh nemaji, SIS vrati bez tabulky listku;
takove se proste preskoci a nic se za ne nedoplnuje.

Pouziti:
    python3 tools/listky.py             # vsichni kandidati z data/predmety.csv
    python3 tools/listky.py NAIL069     # jen vybrane kody, vypise na obrazovku
    python3 tools/listky.py --kontrola  # porovna paralelky s data/rozvrh.csv

HTML se cachuje v zdroje/rozvrhy/html/<KOD>-<skr>-<sem>.html.
"""
import argparse, csv, html as htmlmod, os, re, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "zdroje", "rozvrhy", "html")
URL = ("https://is.cuni.cz/studium/rozvrhng/roz_predmet_macro.php"
       "?fak=11320&skr={skr}&sem={sem}&predmet={kod}{ustav}")
HLAVICKA = ["kod", "paralelka", "typ", "jazyk", "zapsano", "kapacita", "skupiny"]
ZS, LS = "1", "2"
VRSTVY = ("A", "B", "C")


def stahni(kod, skr, sem, ustav="", obnovit=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{kod}-{skr}-{sem}.html")
    if obnovit or not os.path.exists(path):
        url = URL.format(skr=skr, sem=sem, kod=kod,
                         ustav=f"&ustav={ustav}" if ustav else "")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
    return open(path, "rb").read().decode("utf-8", "replace")


def text(kus):
    """Bunka tabulky -> holy text (bez tagu, entit a zdvojenych mezer)."""
    kus = re.sub(r"<[^>]*>", " ", kus)
    return re.sub(r"\s+", " ", htmlmod.unescape(kus)).strip()


def skupiny(bunka):
    """Studijni skupiny jsou schovane v bublinovem hintu posledniho sloupce."""
    m = re.search(r"ShowHint\('hint',this\.id,0,'(.*?)'\);", bunka, re.S)
    if not m:
        return text(bunka)
    kody = re.findall(r"([MNB]#[A-Za-z0-9]+)", htmlmod.unescape(m.group(1)))
    return " ".join(dict.fromkeys(kody))


def parsuj(kod, html):
    """Radky tabulky listku. Kdyz predmet rozvrh nema, tabulka na strance neni."""
    i = html.find("Skupiny</th>")
    if i < 0:
        return []
    telo = html[i:].split("</table>")[0]
    out = []
    for radek in re.findall(r'<tr class="row\d"[^>]*>(.*?)</tr>', telo, re.S):
        bunky = re.findall(r"<td[^>]*>(.*?)</td>", radek, re.S)
        if len(bunky) < 11:
            continue
        listek = text(bunky[0])
        if not listek.startswith(("2", "1")) or kod not in listek:
            continue
        pocty = re.match(r"(\d+)(?:\s*\((\d+)\))?", text(bunky[8]))
        out.append({
            "kod": kod,
            "paralelka": listek,
            "typ": text(bunky[1]),
            "jazyk": text(bunky[7]),
            "zapsano": pocty.group(1) if pocty else "",
            "kapacita": (pocty.group(2) or "") if pocty else "",
            "skupiny": skupiny(bunky[10]),
        })
    return out


def ustav_z_sis():
    """Nektere predmety SIS bez ustavu nenajde - stejny fallback jako rozvrh.py."""
    p = os.path.join(D, "sis.csv")
    out = {}
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            m = re.search(r"\((32-[A-Z]+)\)", r.get("pracoviste", ""))
            if m:
                out[r["kod"]] = m.group(1)
    return out


def kandidati():
    src = os.path.join(D, "predmety.csv")
    return [r["kod"] for r in csv.DictReader(open(src, encoding="utf-8"))
            if r["vrstva"] in VRSTVY]


def kontrola(skr, sem):
    """Kazda paralelka z listku ma byt i v rozvrhu a naopak."""
    p = os.path.join(D, "rozvrh.csv")
    if not os.path.exists(p):
        print("data/rozvrh.csv neexistuje, kontrola preskocena")
        return
    roz = {r["paralelka"] for r in csv.DictReader(open(p, encoding="utf-8"))
           if r["skr"] == skr and r["sem"] == sem}
    lis = {r["paralelka"] for r in
           csv.DictReader(open(os.path.join(D, "listky.csv"), encoding="utf-8"))}
    print(f"rozvrh.csv: {len(roz)} paralelek, listky.csv: {len(lis)}, "
          f"prunik: {len(roz & lis)}")
    if lis - roz:
        print("jen v listky.csv: " + ", ".join(sorted(lis - roz)))
    if roz - lis:
        print("jen v rozvrh.csv: " + ", ".join(sorted(roz - lis)))
    if lis == roz:
        print("parovani sedi")


def main():
    ap = argparse.ArgumentParser(description="Jazyk a kapacita rozvrhovych listku")
    ap.add_argument("kody", nargs="*", help="jen vybrane kody - vypise na obrazovku")
    ap.add_argument("--skr", default="2026", help="akademicky rok, 2026 = 2026/27")
    ap.add_argument("--sem", default=ZS, choices=[ZS, LS], help="1 = zimni, 2 = letni")
    ap.add_argument("--obnovit", action="store_true", help="ignoruj cache")
    ap.add_argument("--kontrola", action="store_true",
                    help="jen porovnej paralelky s data/rozvrh.csv")
    a = ap.parse_args()

    if a.kontrola:
        kontrola(a.skr, a.sem)
        return

    ustavy = ustav_z_sis()

    def listky(kod):
        r = parsuj(kod, stahni(kod, a.skr, a.sem, "", a.obnovit))
        # bez parametru ustav SIS u nekterych predmetu tabulku nevypise
        if not r and ustavy.get(kod):
            r = parsuj(kod, stahni(kod, a.skr, a.sem, ustavy[kod], True))
        return r

    if a.kody:
        for kod in a.kody:
            for r in listky(kod):
                print(" ".join(f"{r[k]}" for k in HLAVICKA))
        return

    kody = kandidati()
    radky, prazdne = [], []
    for kod in kody:
        nove = listky(kod)
        (radky.extend(nove) if nove else prazdne.append(kod))
        print(".", end="", flush=True)
    out = os.path.join(D, "listky.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, HLAVICKA)
        w.writeheader()
        w.writerows(sorted(radky, key=lambda r: (r["kod"], r["paralelka"])))
    print(f"\n{len(radky)} listku -> {out}")
    if prazdne:
        print("bez rozvrhovych listku v tomhle semestru: " + ", ".join(prazdne))
    kontrola(a.skr, a.sem)


if __name__ == "__main__":
    main()
