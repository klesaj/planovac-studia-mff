#!/usr/bin/env python3
"""Stahne verejne vysledky studentske ankety ze SIS.

Anketa je verejna bez prihlaseni, dva pohledy:
    co=1  ciselne hodnoceni vyuky (prumer:smerodatna odchylka, skala 1 = nejlepsi)
    co=2  pripominky k vyuce (volny text)
URL: anketa/index.php?do=vysledky&fak=11320&co=<1|2>&zobraz=1&povinn=<KOD>

Vystup:
    data/anketa_cisla.csv      kod, vyucujici, role, obdobi, odpovedelo, zapsano, <14 kriterii>
    data/anketa_komentare.csv  kod, vyucujici, role, datum, rocnik, program, text
    12-ankety-prehled.md       cteci prehled k rucnimu overeni

Stahuji se **vsechny** predmety z data/predmety.csv (vcetne vrstvy X) a u kazdeho
**vsichni** vyucujici, ktere anketa zna — ne jen ti, kdo uci v aktualnim ZS. Kdo uci kdy,
se rok od roku meni; historie je proto soucast dat, ne sum. Navazuje na ni
tools/ucitele_historie.py, ktere z obdobi ankety spocita, ktere roky kdo ucil.

Pouziti:  python3 tools/anketa.py             # vsechny predmety z data/predmety.csv
          python3 tools/anketa.py NAIL002     # jen jeden
          python3 tools/anketa.py --obnovit   # znovu stahnout, necist cache
"""
import csv, html, os, re, sys, urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "zdroje", "ankety")
URL = ("https://is.cuni.cz/studium/anketa/index.php"
       "?do=vysledky&fak=11320&co={co}&zobraz=1&povinn={kod}")
# poradi sloupcu tabulky "Ciselne hodnoceni vyuky" (skala 1 = nejlepsi, 4 = nejhorsi)
KRITERIA = ["srozumitelnost", "usporadanost", "zajimavost", "vztah_ke_studentum",
            "kvalita_materialu", "korektnost", "obtiznost", "znalosti_studentu",
            "ucast", "priprava", "kazen", "rec", "literatura",
            "_", "celkove_predmet", "celkove_vyucujici", "otazka19"]
CISLA_HL = (["kod", "vyucujici", "role", "obdobi", "odpovedelo", "zapsano"]
            + [k for k in KRITERIA if k != "_"])
KOM_HL = ["kod", "vyucujici", "role", "datum", "rocnik", "program", "text"]
JMENO = re.compile(r"^(?:prof\.|doc\.|RNDr\.|Mgr\.|Ing\.|Bc\.|MUDr\.|PhDr\.|M\.Sc\.|)\s*"
                   r"[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][^,]{1,30},")
PREDMET = re.compile(r"^(.*?)\s*\[([A-Z]{4}\d{3}),\s*([^\]]+)\]")


class Tabulky(HTMLParser):
    """Vytahne radky vsech tabulek jako seznamy textu bunek (zvlada vnorene tabulky)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.radky, self._bunky, self._text, self._hloubka = [], None, [], 0

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._bunky = []
        elif tag in ("td", "th"):
            self._text = []
            self._hloubka = 1

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._bunky is not None:
            self._bunky.append(re.sub(r"\s+", " ", "".join(self._text)).strip())
            self._hloubka = 0
        elif tag == "tr" and self._bunky is not None:
            if any(self._bunky):
                self.radky.append(self._bunky)
            self._bunky = None

    def handle_data(self, data):
        if self._hloubka:
            self._text.append(data)


def stahni(kod, co, obnovit=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{kod}-co{co}.html")
    if obnovit or not os.path.exists(path):
        req = urllib.request.Request(URL.format(co=co, kod=kod),
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            data = r.read()
        open(path, "wb").write(data)
    return open(path, "rb").read().decode("utf-8", "replace")


def radky(html_text):
    p = Tabulky()
    p.feed(html_text)
    return p.radky


def cisla(kod, html_text):
    """Radek = predmet [KOD, role] | obdobi | n/x/zapsano | 14x prumer + :odchylka."""
    out, ucitel = [], ""
    for r in radky(html_text):
        prvni = r[0] if r else ""
        if JMENO.match(prvni) and "[" not in prvni:
            ucitel = prvni
            continue
        m = PREDMET.match(prvni)
        if not m or m.group(2) != kod:
            continue
        hodnoty = []
        for c in r[3:]:                       # bunka ma tvar "prumer:odchylka"
            m2 = re.match(r"^(\d+,\d+):", c)
            hodnoty.append(m2.group(1) if m2 else "")
        pocet = re.match(r"(\d+)/(\d+)/(\d+)", r[2] or "")
        zaznam = {"kod": kod, "vyucujici": ucitel, "role": m.group(3),
                  "obdobi": r[1], "odpovedelo": pocet.group(1) if pocet else "",
                  "zapsano": pocet.group(3) if pocet else ""}
        for i, k in enumerate(KRITERIA):
            if k == "_":
                continue
            zaznam[k] = hodnoty[i] if i < len(hodnoty) and hodnoty[i] != "0,00" else ""
        out.append(zaznam)
    return out


HLAVA = re.compile(r'class="head2"[^>]*>(.*?)</td>', re.S)
META = re.compile(r'class="row2"[^>]*>(.*?)</td>', re.S)
TEXT = re.compile(r'class="row"[^>]*>(.*?)</td>', re.S)
BLOK = re.compile(r'class="head2"')


def cist(kus):
    """Odstroji HTML a rozkoduje entity (&quot; a spol.), at v textu nezustanou."""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", kus))).strip()


# hlavicka bloku pripominek. Tri tvary, ktere SIS pouziva:
#   "prof. Jan Novak [32-KTIML], Nazev [KOD, role]"  — pripominka k vyucujicimu
#   "Připomínka k předmětu, Nazev [KOD, role]"       — pripominka k predmetu jako celku
#   "---, Nazev [KOD, role]"                          — vyucujici neuveden
# Prvni varianta se zkousi driv: bez ni by se ", Ph.D." odlouplo od jmena.
HLAVICKA_UCITEL = re.compile(r"^(.*?)\s*\[32-[A-Z]+\],\s*(.*?)\s*"
                             r"\[([A-Z]{4}\d{3}),\s*([^\]]+)\]")
HLAVICKA = re.compile(r"^(.*?),\s*(.*?)\s*\[([A-Z]{4}\d{3}),\s*([^\]]+)\]")
BEZ_UCITELE = ("Připomínka k předmětu", "---", "")


def komentare(kod, html_text):
    """Blok = hlavicka 'Ucitel [32-XXX], Nazev [KOD, role]', pak dvojice row2 (kdo/kdy) + row (text)."""
    out = []
    casti = re.split(r'(?=<td class="head2")', html_text)
    for cast in casti:
        h = HLAVA.search(cast)
        if not h:
            continue
        hlava = cist(h.group(1))
        m = HLAVICKA_UCITEL.search(hlava) or HLAVICKA.search(hlava)
        if not m or m.group(3) != kod:
            continue
        ucitel, role = m.group(1).strip(), m.group(4)
        if ucitel in BEZ_UCITELE:
            ucitel = ""            # pripominka k predmetu, ne k cloveku
        metas = [cist(x) for x in META.findall(cast)]
        texty = [cist(x) for x in TEXT.findall(cast)]
        for meta, text in zip(metas, texty):
            d = re.search(r"(\d{2}\.\d{2}\.\d{4}), ([^,]+), (.+?), (?:bakalářské|navazující magisterské|magisterské|doktorské)", meta)
            if len(text) < 10:
                continue
            out.append({"kod": kod, "vyucujici": ucitel, "role": role,
                        "datum": d.group(1) if d else "", "rocnik": d.group(2) if d else "",
                        "program": d.group(3) if d else "", "text": text})
    return out


def main():
    args = sys.argv[1:]
    obnovit = "--obnovit" in args
    kody = [a for a in args if not a.startswith("-")]
    if not kody:
        # vsechny predmety, i vrstva X — anketa je duvod, proc se nekterý muze vratit
        kody = [r["kod"] for r in csv.DictReader(open(os.path.join(D, "predmety.csv"),
                                                      encoding="utf-8"))]
    vsechna_cisla, vsechny_kom = [], []
    for kod in kody:
        vsechna_cisla += cisla(kod, stahni(kod, 1, obnovit))
        vsechny_kom += komentare(kod, stahni(kod, 2, obnovit))
        print(".", end="", flush=True)
    for jmeno, hl, data in [("anketa_cisla.csv", CISLA_HL, vsechna_cisla),
                            ("anketa_komentare.csv", KOM_HL, vsechny_kom)]:
        with open(os.path.join(D, jmeno), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, hl)
            w.writeheader()
            w.writerows(data)
    print(f"\n{len(vsechna_cisla)} radku cisel, {len(vsechny_kom)} komentaru "
          f"-> data/anketa_cisla.csv, data/anketa_komentare.csv")


if __name__ == "__main__":
    main()
