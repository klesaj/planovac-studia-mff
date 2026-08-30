#!/usr/bin/env python3
"""Postavi z data/*.csv citelnou HTML stranku -> artifact/plan.html

Stranka ma dve urovne:
  * prehled  - tydenni mrizka ZS a dlazdice predmetu (lidske nazvy, kody druhotne)
  * detail   - jedna sekce na predmet: proc ho chci, o cem je, rozvrh, ucitele
               serazeni podle ankety od nejlepsiho po nejhorsiho, odkazy do SIS

Prepinani je pres #hash, takze detail predmetu ma vlastni odkaz a funguje zpet/vpred.
Publikuje se nastrojem Artifact na stalou URL (viz CLAUDE.md).
"""
import csv, html, json, os, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "artifact", "plan.html")
import program as _cfg

# Vsechno, co zavisi na programu a zamereni, prichazi z data/program.json.
# Defaulty v druhem argumentu drzi skript pri zivote, kdyz konfigurace chybi.
SKR, SEM = _cfg.semestr(("2026", "1"))
SIS_PREDMET = "https://is.cuni.cz/studium/predmety/index.php?do=predmet&kod={kod}"
SIS_ROZVRH = ("https://is.cuni.cz/studium/rozvrhng/roz_predmet_macro.php"
              "?fak=11320&skr=" + SKR + "&sem=" + SEM + "&predmet={kod}")
SIS_ANKETA = ("https://is.cuni.cz/studium/anketa/index.php?do=vysledky&fak=11320"
              "&co={co}&zobraz=1&povinn={kod}")
DNY = ["Po", "Út", "St", "Čt", "Pá"]
SKUPINY = _cfg.skupiny([("povinny", "povinný", 47), ("profilujici", "profilující", 38),
                        ("rozsirujici", "rozšiřující", 15), ("volitelny", "volitelný", 0)])
NAZEV_SK = {k: n for k, n, _ in SKUPINY}
SKUPINA_MNOZ = {"povinny": "Povinné předměty", "profilujici": "Profilující předměty",
                "rozsirujici": "Rozšiřující předměty", "volitelny": "Volitelné předměty"}
SZZ = _cfg.szz_nazvy({"SU": "Strojové učení a jeho aplikace", "NS": "Neuronové sítě",
                      "DZ": "Dobývání znalostí"})
# doporucene predmety jednotlivych okruhu podle studijniho planu (Karolinka 2025/26)
SZZ_DOPORUCENE = _cfg.szz_doporucene(
    {"SU": ["NAIL029", "NPFL147", "NAIL025", "NAIL107"],
     "NS": ["NAIL002", "NAIL060", "NAIL013", "NAIL065"],
     "DZ": ["NDBI023", "NAIL116", "NAIL105", "NAIL099"]})
MINIMA = _cfg.minima({"povinny": 47, "profilujici": 38,
                      "rozsirujici": 15, "volitelny": 0})
ZAMERENI = _cfg.zamereni_seznam()
NAZEV_ZAMERENI = dict(ZAMERENI)
# Ucebny: S / SU / SW jsou Mala Strana (Malostranske nam. 25),
# K jsou Karlin (Sokolovska 49/83) - overeno na webu MFF.
BUDOVY = [("K", "Karlín", "Sokolovská 49/83, Praha 8"),
          ("S", "Malá Strana", "Malostranské nám. 25, Praha 1")]
VRSTVY = {"A": "doporučeno plánem", "B": "vlastní jádro",
          "C": "kandidát", "X": "nedostupný"}
# stupnice dochazky ze stranek kurzu (data/stranky.csv) — od nejmene po nejvic svazujici
DOCHAZKA = {
    "nerelevantni": ("jen přednáška", "Cvičení nemá, docházka se neřeší.", "neutral"),
    "neresi_se": ("docházka se neřeší", "Na hodiny chodit nemusíš.", "dobra"),
    "doporucena": ("docházka doporučená", "Nekontroluje se, ale bez ní to bolí.", "neutral"),
    "bodovana": ("docházka bodovaná", "Za účast se sbírají body — chození ovlivňuje zápočet.", "stredni"),
    "povinna": ("docházka povinná", "Bez chození zápočet nedostaneš.", "slaba"),
    "nezjisteno": ("docházka nezjištěna", "Nepodařilo se dohledat, ověř před zápisem.", "neutral"),
}
# siroke tematicke oblasti pro filtrovani dlazdic (data/tagy.csv, pise agent)
TAGY = [("ml", "strojové učení"), ("nn", "neuronové sítě"), ("nlp", "jazyk a text"),
        ("videni", "obraz a vidění"), ("rl", "zpětnovazební učení"),
        ("stat", "pravděpodobnost a statistika"), ("data", "data a znalosti"),
        ("evoluce", "evoluce a optimalizace"), ("grafy", "grafy a sítě"),
        ("teorie", "teorie a algoritmy"), ("ai", "klasická UI"),
        ("bio", "bio a neurověda"), ("praxe", "projekty a praxe"),
        ("diplomka", "diplomka")]
NAZEV_TAGU = dict(TAGY)
SEMESTR_CIP = {"zimní": "zimní semestr", "letní": "letní semestr", "oba": "zimní i letní"}
NAHRAVKY = {"ano": "nahrávky přednášek", "castecne": "materiály částečně",
            "ne": "bez nahrávek", "nezjisteno": ""}
E = html.escape


def nacti(jmeno):
    p = os.path.join(D, jmeno)
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


def klic(jmeno):
    """'Barták Roman' i 'prof. RNDr. Roman Barták, Ph.D.' -> {'barták','roman'}"""
    return frozenset(w.lower() for w in re.split(r"[,\s]+", jmeno or "")
                     if w and "." not in w and len(w) > 1)


def prijmeni(jmeno):
    """'Barták Roman' -> 'Barták Roman'; 'prof. RNDr. Roman Barták, Ph.D.' -> 'Roman Barták'"""
    slova = [w for w in re.split(r"[,\s]+", jmeno or "") if w and "." not in w and len(w) > 1]
    return " ".join(slova)


def minuty(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def cislo(s):
    try:
        return float((s or "").replace(",", "."))
    except ValueError:
        return None


def rok(obdobi):
    m = re.match(r"\s*(\d{4})", obdobi or "")
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------- nacteni dat
def data():
    sis = {r["kod"]: r for r in nacti("sis.csv")}
    rel = {r["kod"]: r for r in nacti("relevance.csv")}
    anot = {r["kod"]: r for r in nacti("anotace.csv")}
    listky = {r["paralelka"]: r for r in nacti("listky.csv")}
    vyklad = {r["kod"]: r for r in nacti("vyklad_zs.csv") + nacti("vyklad_ls.csv")}
    stranky = {r["kod"]: r for r in nacti("stranky.csv")}
    tagy = {r["kod"]: [t.strip() for t in (r["tagy"] or "").split("|") if t.strip()]
            for r in nacti("tagy.csv")}
    ank_predmet = {r["kod"]: r for r in nacti("anketa_predmet.csv")}
    shrnuti = defaultdict(list)
    for r in nacti("anketa_shrnuti.csv"):
        shrnuti[(r["kod"], klic(r["vyucujici"]), r["role"])].append(r)
    kurzy = {}
    for r in nacti("predmety.csv"):
        k = r["kod"]
        s, a = sis.get(k, {}), anot.get(k, {})
        kurzy[k] = {
            "kod": k, "vrstva": r["vrstva"], "skupina": r["skupina"], "szz": r["szz"],
            "zamereni": [z.strip() for z in (r.get("zamereni") or "vse").split("|")
                         if z.strip()] or ["vse"],
            "stav_plan": r["stav"], "poznamka": r["poznamka"],
            "plan_semestr": r["plan_semestr"],
            "nazev": s.get("nazev", k), "anglicky": s.get("anglicky", ""),
            "kredity": int(s.get("kredity") or 0), "rozsah": s.get("rozsah", ""),
            "examinace": s.get("examinace", ""), "semestr": s.get("semestr", ""),
            "stav_sis": s.get("stav", ""), "pracoviste": s.get("pracoviste", ""),
            "garant": s.get("garant", ""), "vyucujici": s.get("vyucujici", "") or s.get("garant", ""),
            "neslucitelnost": s.get("neslucitelnost", ""),
            "zkratka": rel.get(k, {}).get("zkratka") or s.get("nazev", k),
            "relevance": rel.get(k, {}).get("relevance", ""),
            "anotace": a.get("anotace", ""), "sylabus": a.get("sylabus", ""),
            "podminky": a.get("podminky", ""), "vyklad": vyklad.get(k, {}),
            "stranka": stranky.get(k, {}),
            "tagy": [t for t in tagy.get(k, []) if t in NAZEV_TAGU],
            "anketa_predmet": ank_predmet.get(k, {}),
            "cisla_predmet": [],
            "bloky": [], "ucitele": {}, "listky_bez_casu": [],
            "komentare_predmet": [],
        }
    for b in nacti("rozvrh.csv"):
        if b["kod"] in kurzy:
            b.update({kk: vv for kk, vv in listky.get(b["paralelka"], {}).items()
                      if kk in ("jazyk", "zapsano", "kapacita", "skupiny")})
            kurzy[b["kod"]]["bloky"].append(b)
    for l in nacti("listky.csv"):
        k = kurzy.get(l["kod"])
        if k is not None and l["paralelka"] not in {b["paralelka"] for b in k["bloky"]}:
            # listek bez casu a ucebny — CSV export rozvrhu ho vubec nevraci
            if not re.search(r"p\d+b$", l["paralelka"]):   # druhy tydenni blok tehoz listku
                k["listky_bez_casu"].append(l)
    # Vyucujici: vsichni, ktere anketa u predmetu zna (data/ucitele_historie.csv),
    # ne jen ti z rozvrhu ZS 2026/27 — obsazeni se rok od roku meni a historie
    # ("kdo se tam toci") je pro planovani stejne dulezita jako aktualni stav.
    for h in nacti("ucitele_historie.csv"):
        if h["kod"] not in kurzy or not h["vyucujici"]:
            continue                    # prazdne jmeno = pripominky k predmetu jako celku
        z = kurzy[h["kod"]]["ucitele"].setdefault(
            klic(h["vyucujici"]), {"jmeno": h["vyucujici"], "role": set(),
                                   "cisla": [], "komentare": [], "roky": set(),
                                   "role_zs": set(), "uci_v_zs": False,
                                   "posledni_rok": 0, "prvni_rok": 0})
        z["role"].add(h["role"])
        z["uci_v_zs"] = z["uci_v_zs"] or h["uci_v_zs"] == "1"
        z["roky"] |= {x for x in (h["roky"] or "").split("|") if x}
        for pole in ("posledni_rok", "prvni_rok"):
            if h[pole]:
                z[pole] = (max(z[pole], int(h[pole])) if pole == "posledni_rok"
                           else min(z[pole] or 9999, int(h[pole])))
    for u in nacti("ucitele.csv"):       # jmeno z rozvrhu je citelnejsi nez z ankety
        z = kurzy.get(u["kod"], {}).get("ucitele", {}).get(klic(u["ucitel"]))
        if z is not None:
            z["jmeno"], z["uci_v_zs"] = u["ucitel"], True
            z["role"].add(u["role"])
            z["role_zs"].add(u["role"])
    for c in nacti("anketa_cisla.csv"):
        if c["kod"] in kurzy:
            kurzy[c["kod"]]["cisla_predmet"].append(c)
        u = kurzy.get(c["kod"], {}).get("ucitele", {}).get(klic(c["vyucujici"]))
        if u and rok(c["obdobi"]) >= 2016:
            u["cisla"].append(c)
    for k in nacti("anketa_komentare.csv"):
        if k["kod"] not in kurzy:
            continue
        if not k["vyucujici"]:           # pripominka k predmetu, ne k cloveku
            kurzy[k["kod"]]["komentare_predmet"].append(k)
            continue
        u = kurzy[k["kod"]]["ucitele"].get(klic(k["vyucujici"]))
        if u:
            u["komentare"].append(k)
    for kod, kurz in kurzy.items():
        for kl, u in kurz["ucitele"].items():
            u["shrnuti"] = [r for role in u["role"] for r in shrnuti.get((kod, kl, role), [])]
    for kurz in kurzy.values():
        for u in kurz["ucitele"].values():
            hodnoty = [cislo(c["celkove_predmet"]) for c in sorted(
                u["cisla"], key=lambda c: -rok(c["obdobi"]))[:6]]
            hodnoty = [h for h in hodnoty if h is not None]
            u["prumer"] = sum(hodnoty) / len(hodnoty) if hodnoty else None
            u["odpovedi"] = sum(int(c["odpovedelo"] or 0) for c in u["cisla"][:6])
    for kurz in kurzy.values():
        # hodnoceni predmetu jako celku: vazeny prumer pres vsechny vyucujici
        # a role tri nejnovejsich obdobi, ktera SIS k predmetu ma
        radky = sorted(kurz["cisla_predmet"], key=lambda c: -rok(c["obdobi"]))
        obdobi = sorted({rok(c["obdobi"]) for c in radky}, reverse=True)[:3]
        vzorek = [c for c in radky if rok(c["obdobi"]) in obdobi]
        vahy = [(cislo(c["celkove_predmet"]), int(c["odpovedelo"] or 0)) for c in vzorek]
        vahy = [(h, w) for h, w in vahy if h is not None and w > 0]
        kurz["prumer_predmet"] = (sum(h * w for h, w in vahy) / sum(w for _, w in vahy)
                                  if vahy else None)
        kurz["odpovedi_predmet"] = sum(w for _, w in vahy)
        kurz["obdobi_predmet"] = ([str(min(obdobi)), str(max(obdobi))] if obdobi else [])
    return kurzy


# ---------------------------------------------------------------- kousky HTML
def odkazy(kod, tridy="odkazy"):
    return (f'<p class="{tridy}">'
            f'<a href="{SIS_PREDMET.format(kod=kod)}" target="_blank" rel="noopener">'
            f'SIS: předmět</a>'
            f'<a href="{SIS_ROZVRH.format(kod=kod)}" target="_blank" rel="noopener">'
            f'SIS: rozvrh ZS</a>'
            f'<a href="{SIS_ANKETA.format(co=2, kod=kod)}" target="_blank" rel="noopener">'
            f'SIS: připomínky z ankety</a>'
            f'<a href="{SIS_ANKETA.format(co=1, kod=kod)}" target="_blank" rel="noopener">'
            f'SIS: číselné hodnocení</a></p>')


def odrazky(text, trida=""):
    polozky = [x.strip() for x in (text or "").split("|") if x.strip()]
    if not polozky:
        return ""
    return (f'<ul class="body {trida}">'
            + "".join(f"<li>{E(x)}</li>" for x in polozky) + "</ul>")


def budova(mistnost):
    for prefix, nazev, adresa in BUDOVY:
        if (mistnost or "").upper().startswith(prefix):
            return nazev, adresa
    return "", ""


def des(x):
    """1.37 -> '1,37' (desetinna carka, ne teckou nahrazovanou v cele HTML znacce)"""
    return f"{x:.2f}".replace(".", ",")


def znamka_trida(p):
    if p is None:
        return "bez"
    return "dobra" if p < 1.6 else ("stredni" if p < 2.3 else "slaba")


def cip(text, trida=""):
    return f'<span class="chip {trida}">{text}</span>'


def semestr_znacka(k):
    """'zimní' -> ' · ZS' modre, 'letní' -> ' · LS' zelene, 'oba' -> obojí."""
    kusy = {"zimní": [("ZS", "zima")], "letní": [("LS", "leto")],
            "oba": [("ZS", "zima"), ("LS", "leto")]}.get(k["semestr"], [])
    if not kusy:
        return ""
    return " · " + " ".join(f'<b class="sem-znak {t}">{z}</b>' for z, t in kusy)


def dlazdice(k):
    chips = []
    if k["szz"] != "-":
        chips.append(cip(f'SZZ · {SZZ.get(k["szz"], k["szz"])}', "szz"))
    if k["stav_sis"] == "nevyučován":
        chips.append(cip("nevyučován", "varovani"))
    jinde = sorted({budova(b["mistnost"])[0] for b in k["bloky"]} - {"", "Malá Strana"})
    for b in jinde:
        chips.append(cip(b, "budova-chip"))
    st = k.get("stranka") or {}
    if st.get("dochazka") in ("povinna", "bodovana"):
        chips.append(cip(DOCHAZKA[st["dochazka"]][0], "dochazka-chip " + DOCHAZKA[st["dochazka"]][2]))
    if st.get("nahravky") == "ano":
        chips.append(cip("nahrávky", "nahravky-chip"))
    tagy = "".join(cip(NAZEV_TAGU[t], "tag-chip") for t in k["tagy"])
    anketa = ""
    if k["prumer_predmet"] is not None:
        anketa = (f'<p class="dlazdice-anketa">Anketa: '
                  f'<span class="znamka {znamka_trida(k["prumer_predmet"])}">'
                  f'{des(k["prumer_predmet"])}</span> '
                  f'<span class="tlumene">{k["odpovedi_predmet"]} odpovědí</span></p>')
    hledat = " ".join([k["kod"], k["zkratka"], k["nazev"], k["anglicky"],
                       " ".join(NAZEV_TAGU[t] for t in k["tagy"])]).lower()
    return f"""      <div class="dlazdice sk-{k['skupina']}" data-kod="{k['kod']}"
           data-tagy="{E(' '.join(k['tagy']))}" data-semestr="{E(k['semestr'])}"
           data-skupina="{k['skupina']}" data-vrstva="{k['vrstva']}"
           data-zamereni="{E(' '.join(k['zamereni']))}" data-hledat="{E(hledat)}"
           tabindex="0" role="button" aria-pressed="false">
        <header><h3>{E(k['zkratka'])}</h3>
          <span class="vybrano-znacka" aria-hidden="true">v plánu</span>
          <span class="kr">{k['kredity']}<small>kr</small></span></header>
        <p class="kod">{E(k['kod'])} · {E(k['rozsah'])} {E(k['examinace'])}{semestr_znacka(k)}</p>
        <div class="chips">{''.join(chips)}</div>
        {f'<div class="chips tagy">{tagy}</div>' if tagy else ''}
        {anketa}
        <a class="na-detail" href="#p-{k['kod']}">detail předmětu →</a>
      </div>"""


def sekce_dlazdic(zive):
    """Dlazdice po skupinach predmetu (povinne / profilujici / ...), ne podle rozvrhu."""
    out = []
    for slug, nazev, minimum in SKUPINY:
        vybrane = sorted([k for k in zive if k["skupina"] == slug],
                         key=lambda k: (k["vrstva"], -k["kredity"], k["zkratka"]))
        if not vybrane:
            continue
        kr = sum(k["kredity"] for k in vybrane)
        popis = f'{len(vybrane)} předmětů · {kr} kr v nabídce'
        if minimum:
            popis += f' · minimum {minimum} kr'
        out.append(f"""      <section class="skupina-sekce" data-skupina="{slug}">
        <h3 class="skupina-nadpis sk-{slug}">{SKUPINA_MNOZ.get(slug, nazev)}<span>{popis}</span>
          <span class="skupina-vybrano" data-skupina="{slug}" data-min="{minimum}"></span></h3>
        <div class="dlazdice-mriz">
{chr(10).join(dlazdice(k) for k in vybrane)}
        </div>
      </section>""")
    return "\n".join(out)


def prepinac_zamereni(zive):
    """Chipy zamereni. 'vse' = predmet spolecny celemu programu, ten se nefiltruje pryc."""
    pocty = defaultdict(int)
    for k in zive:
        for z in k["zamereni"]:
            pocty[z] += 1
    dostupna = [(kod, nazev) for kod, nazev in ZAMERENI if pocty.get(kod)]
    if len(dostupna) < 2:
        return ""
    chipy = "".join(
        f'<button type="button" class="zam-tlac" data-zam="{E(kod)}">{E(nazev)}'
        f'<span class="tag-pocet">{pocty[kod]}</span></button>'
        for kod, nazev in dostupna)
    return ('<div class="filtr-radek chipy zamereni-radek">'
            '<span class="filtr-popisek">zaměření:</span>' + chipy +
            f'<span class="tlumene">+ {pocty.get("vse", 0)} společných pro celý program</span>'
            '</div>')


def filtr_tagu(zive):
    pocty = defaultdict(int)
    for k in zive:
        for t in k["tagy"]:
            pocty[t] += 1
    chipy = "".join(
        f'<button type="button" class="tag-tlac" data-tag="{slug}">{E(nazev)}'
        f'<span class="tag-pocet">{pocty[slug]}</span></button>'
        for slug, nazev in TAGY if pocty[slug])
    if not chipy:
        return ""
    return f"""      <div class="filtr filtr-dlazdic">
        <div class="filtr-radek">
          <input type="search" id="hledani" placeholder="hledat: název, kód, oblast"
                 aria-label="Hledat v předmětech">
          <label class="filtr-prepinac"><input type="checkbox" id="f-zima"> jen zimní semestr</label>
          <label class="filtr-prepinac"><input type="checkbox" id="f-jadro"> jen doporučené plánem</label>
          <span class="filtr-oddel"></span>
          <button type="button" class="filtr-tlac" id="tagy-vse">zrušit filtr</button>
          <span class="filtr-stav" id="dlazdice-stav"></span>
        </div>
        {prepinac_zamereni(zive)}
        <div class="filtr-radek chipy tagy-radek">{chipy}</div>
      </div>"""


def tabulka_rozvrhu(k):
    bez_casu = ""
    if k["listky_bez_casu"]:
        kusy = ", ".join(f'<code>{E(l["paralelka"])}</code>' for l in k["listky_bez_casu"])
        n = len(k["listky_bez_casu"])
        slovo = "lístek" if n == 1 else ("lístky" if n < 5 else "lístků")
        bez_casu = (f'<p class="prazdno">SIS eviduje {n} {slovo} bez času a učebny '
                    f'({kusy}) — výuka nejspíš po domluvě s vyučujícím.</p>')
    if not k["bloky"]:
        return ('<p class="prazdno">V rozvrhu ZS 2026/27 nemá tenhle předmět '
                'žádný lístek s časem.</p>' + bez_casu)
    radky = []
    for b in sorted(k["bloky"], key=lambda b: (DNY.index(b["den"]) if b["den"] in DNY else 9,
                                               minuty(b["od"]))):
        # pred zapisem je zapsanych vsude 0, takze ukazuju kapacitu, ne obsazenost
        kap = (b.get("kapacita") or "").strip()
        kapacita = f"{kap} míst" if kap not in ("", "0") else "neomezeno"
        if (b.get("zapsano") or "0").strip() not in ("", "0"):
            kapacita = f'{b["zapsano"]} / ' + (kap if kap not in ("", "0") else "∞")
        radky.append(
            f'<tr><td>{E(b["typ"])}</td><td class="c">{E(b["den"])} {E(b["od"])}–{E(b["do"])}</td>'
            f'<td><b>{E(prijmeni(b["ucitel"]))}</b></td><td>{E(b["mistnost"])}</td>'
            f'<td>{E(b["poznamka"])}</td><td class="c">{E(kapacita)}</td>'
            f'<td class="tlumene">{E(b.get("jazyk", ""))}</td>'
            f'<td class="tlumene"><code>{E(b["paralelka"])}</code></td></tr>')
    return (bez_casu + '<div class="tab-obal"><table><thead><tr><th>Typ</th><th class="c">Kdy</th>'
            '<th>Vyučující</th><th>Kde</th><th>Poznámka</th>'
            '<th class="c">Kapacita</th><th>Jazyk</th><th>Lístek</th></tr></thead><tbody>'
            + "".join(radky) + "</tbody></table></div>")


def sekce_predmetu_anketa(k):
    """Co anketa rika o predmetu jako takovem — nad vrstvou vyucujicich."""
    a = k.get("anketa_predmet") or {}
    kp = k.get("komentare_predmet") or []
    if not a and k["prumer_predmet"] is None and not kp:
        return ""
    znamka = ""
    if k["prumer_predmet"] is not None:
        ob = k.get("obdobi_predmet") or []
        obdobi = (ob[0] if len(ob) < 2 or ob[0] == ob[1] else f"{ob[0]}–{ob[1]}")
        znamka = (f'<div class="predmet-znamka"><span class="znamka velka '
                  f'{znamka_trida(k["prumer_predmet"])}">{des(k["prumer_predmet"])}</span>'
                  f'<p>celkové hodnocení předmětu<br><span class="tlumene">'
                  f'{k["odpovedi_predmet"]} odpovědí, {E(obdobi)}</span></p></div>')
    telo = ""
    if a:
        plus = odrazky(a.get("plus", ""), "plusy")
        minus = odrazky(a.get("minus", ""), "minusy")
        telo = ('<div class="shrnuti">'
                + (f'<p class="shrnuti-veta">{E(a.get("souhrn", ""))}</p>'
                   if a.get("souhrn") else "")
                + ('<div class="dvojice">'
                   + (f'<div><h5 class="mini zeleny">Co studenti chválí</h5>{plus}</div>'
                      if plus else "")
                   + (f'<div><h5 class="mini cerveny">Co jim vadí</h5>{minus}</div>'
                      if minus else "")
                   + '</div>' if (plus or minus) else "")
                + (f'<p class="rozpor"><b>Pozor:</b> {E(a["varovani"])}</p>'
                   if a.get("varovani") else "")
                + f'<p class="shrnuti-zdroj">Shrnuto z {E(a.get("komentaru", "?"))} '
                  f'připomínek k předmětu, {E(a.get("od_data", ""))} – '
                  f'{E(a.get("do_data", ""))}.</p></div>')
    syrove = ""
    if kp:
        polozky = "".join(
            f'<li><span class="kdy">{E(c["datum"])} · {E(c["rocnik"])} · '
            f'{E(c["role"])}</span>{E(c["text"])}</li>'
            for c in sorted(kp, key=lambda c: c["datum"][-4:] + c["datum"][3:5],
                            reverse=True))
        syrove = (f'<details class="kom-predmet"><summary>{len(kp)} '
                  f'{"připomínka" if len(kp) == 1 else "připomínek"} vedená v anketě '
                  f'přímo u předmětu, ne u vyučujícího</summary>'
                  f'<ul class="komentare">{polozky}</ul></details>')
    return ('<h3 class="podnadpis">Co anketa říká o předmětu</h3>'
            '<p class="vysvetlivka">Připomínky, které mluví o předmětu jako takovém — '
            'obtížnost, cvičení, úkoly, bodování — bez ohledu na to, pod kterým '
            'vyučujícím je anketa vede. Hodnocení jednotlivých lidí je níž.</p>'
            f'<div class="predmet-anketa">{znamka}{telo}</div>{syrove}')


def role_ucitele(u):
    """Co uci ted × co o nem vi anketa — role se casem meni, at to neni slepenec."""
    ted, vse = sorted(u.get("role_zs") or []), sorted(u["role"])
    if ted and set(ted) != set(vse):
        drive = [r for r in vse if r not in ted]
        return f"teď {', '.join(ted)} · dřív {', '.join(drive)}"
    return ", ".join(vse)


def roky_ucitele(u):
    """'2019Z|2021Z' -> citelna veta o tom, kdy predmet ucil a jak casto."""
    znacky = {r for r in u.get("roky", set()) if r[:4].isdigit()}
    roky = sorted({int(r[:4]) for r in znacky})
    if not roky:
        return ""
    rozsah = str(roky[0]) if len(roky) == 1 else f"{roky[0]}–{roky[-1]}"
    kolik = f"{len(roky)}× " if len(roky) > 1 else ""
    vyjmenovat = ", ".join(str(r) for r in roky)
    # rok bez Z/L pochazi z data pripominky, ne z obdobi anketniho zaznamu — odhad
    odhad = "" if any(r[-1] in "ZL" for r in znacky) else ", odhad z dat připomínek"
    return (f'<p class="roky" title="{E(vyjmenovat)}">Učil {rozsah} '
            f'<span class="tlumene">({kolik}podle ankety: {E(vyjmenovat)}{odhad})</span></p>')


def clanek_ucitele(u, i):
    znamka = (f'<span class="znamka velka {znamka_trida(u["prumer"])}">'
              f'{u["prumer"]:.2f}'.replace(".", ",", 1) + "</span>"
              ) if u["prumer"] is not None else \
        '<span class="znamka velka bez">bez dat</span>'
    radky = "".join(
        f'<tr><td>{E(c["obdobi"])}</td><td>{E(c["role"])}</td>'
        f'<td class="c">{E(c["odpovedelo"])}/{E(c["zapsano"])}</td>'
        f'<td class="c">{E(c["celkove_predmet"] or "—")}</td>'
        f'<td class="c">{E(c["srozumitelnost"] or "—")}</td>'
        f'<td class="c">{E(c["obtiznost"] or "—")}</td></tr>'
        for c in sorted(u["cisla"], key=lambda c: -rok(c["obdobi"]))[:8])
    tabulka = (f'<div class="tab-obal uzka"><table><thead><tr><th>Období</th><th>Role</th>'
               f'<th class="c">Odpovědí</th><th class="c">Celkové</th>'
               f'<th class="c">Srozum.</th><th class="c">Obtížnost</th></tr></thead>'
               f'<tbody>{radky}</tbody></table></div>') if radky else ""
    shrn = ""
    for r in u.get("shrnuti", []):
        plus = odrazky(r.get("plus", ""), "plusy")
        minus = odrazky(r.get("minus", ""), "minusy")
        rozpor = (f'<p class="rozpor"><b>Rozpor v hodnocení:</b> {E(r["rozpor"])}</p>'
                  if r.get("rozpor") else "")
        shrn += (f'<div class="shrnuti">'
                 f'<p class="shrnuti-veta">{E(r.get("souhrn", ""))}</p>'
                 + ('<div class="dvojice">'
                    + (f'<div><h5 class="mini zeleny">Co studenti chválí</h5>{plus}</div>'
                       if plus else "")
                    + (f'<div><h5 class="mini cerveny">Co jim vadí</h5>{minus}</div>'
                       if minus else "")
                    + '</div>' if (plus or minus) else "")
                 + rozpor
                 + f'<p class="shrnuti-zdroj">Shrnuto z {E(r.get("komentaru","?"))} '
                   f'připomínek, {E(r.get("od_data",""))} – {E(r.get("do_data",""))}.</p>'
                 f'</div>')
    komentare = ""
    if u["komentare"]:
        polozky = "".join(
            f'<li><span class="kdy">{E(c["datum"])} · {E(c["rocnik"])} · '
            f'{E(c["role"])}</span>{E(c["text"])}</li>'
            for c in sorted(u["komentare"], key=lambda c: c["datum"][-4:] + c["datum"][3:5],
                            reverse=True))
        komentare = (f'<details><summary>{len(u["komentare"])} '
                     f'{"připomínka" if len(u["komentare"]) == 1 else "připomínek"} '
                     f'z ankety</summary><ul class="komentare">{polozky}</ul></details>')
    else:
        komentare = '<p class="prazdno">Žádné připomínky v anketě.</p>'
    odznak = ('<span class="odznak-zs">učí v ZS 2026/27</span>' if u.get("uci_v_zs")
              else '<span class="odznak-drive">teď neučí</span>')
    return f"""        <article class="ucitel{'' if u.get('uci_v_zs') else ' drive'}">
          <header><span class="poradi">{i}</span>
            <div><h4>{E(prijmeni(u['jmeno']))} {odznak}</h4>
              <p class="role">{E(role_ucitele(u))} · {u['odpovedi']} odpovědí v anketě</p>
              {roky_ucitele(u)}</div>
            {znamka}</header>
          {shrn}{tabulka}{komentare}
        </article>"""


def sekce_ucitelu(k):
    if not k["ucitele"]:
        return ""
    poradi = sorted(k["ucitele"].values(),
                    key=lambda u: (not u.get("uci_v_zs"), u["prumer"] is None,
                                   u["prumer"] or 9))
    ted = [u for u in poradi if u.get("uci_v_zs")]
    drive = [u for u in poradi if not u.get("uci_v_zs")]
    drive.sort(key=lambda u: (-u.get("posledni_rok", 0), u["prumer"] or 9))
    hlavni = "".join(clanek_ucitele(u, i) for i, u in enumerate(ted, 1))
    if not ted:
        hlavni = ('<p class="prazdno">V rozvrhu ZS 2026/27 u tohohle předmětu '
                  'nikdo nefiguruje — buď se letos neučí, nebo SIS rozvrh ještě '
                  'nevypsal. Níž jsou lidé, které u něj zná anketa.</p>')
    starsi = ""
    if drive:
        starsi = (f'<details class="drivejsi"><summary>Dřívější vyučující '
                  f'({len(drive)}) — kdo předmět učil v minulých letech</summary>'
                  + "".join(clanek_ucitele(u, i) for i, u in enumerate(drive, 1))
                  + '</details>')
    return ('<h3 class="podnadpis">Vyučující podle ankety</h3>'
            '<p class="vysvetlivka">Nahoře lidé z rozvrhu ZS 2026/27, pod nimi všichni '
            'ostatní, které u předmětu zná anketa — obsazení se rok od roku mění, takže '
            'i historie něco říká. U každého je vidět, ve kterých letech předmět učil. '
            'Seřazeno od nejlépe hodnoceného. Škála 1 = nejlepší, '
            '4 = nejhorší; průměr počítám z posledních šesti záznamů, které SIS k té '
            'dvojici předmět + vyučující má. Anketa u garanta ukazuje i připomínky '
            'k ostatním vyučujícím, takže u sporných případů je lepší kouknout do SIS.</p>'
            + hlavni + starsi)


def dblok(html, trida=""):
    """Jeden tematicky blok detailu — nadpis a jeho obsah drzi pohromade."""
    if not (html or "").strip():
        return ""
    return f'<section class="detail-blok {trida}">{html}</section>'


def detail(k, kurzy):
    meta = [f'{k["kredity"]} kreditů', k["rozsah"] + " " + k["examinace"],
            k["semestr"] + " semestr", NAZEV_SK.get(k["skupina"], k["skupina"])]
    if k["szz"] != "-":
        meta.append("SZZ okruh " + SZZ.get(k["szz"], k["szz"]))
    jazyky = {b.get("jazyk", "").strip() for b in k["bloky"] if b.get("jazyk")}
    jazyk_pruh = ""
    if jazyky and jazyky != {"čeština"}:
        meta_jazyk = "anglicky" if jazyky == {"angličtina"} else "česky i anglicky"
        jazyk_pruh = f'<span class="meta-jazyk">výuka {meta_jazyk}</span>' 
    mimo = sorted({budova(b["mistnost"]) for b in k["bloky"]} - {("", ""), ("Malá Strana", "Malostranské nám. 25, Praha 1")})
    budova_pruh = "".join(
        f'<p class="jinde-pruh">Učí se v budově <b>{E(n)}</b> ({E(a)}), '
        f'ne na Malé Straně — počítej s přesunem.</p>' for n, a in mimo)
    varovani = ""
    if k["stav_sis"] == "nevyučován":
        varovani = ('<p class="varovani-pruh">SIS vede tenhle předmět jako '
                    '<b>nevyučovaný</b> — počítat s tím, že se neotevře.</p>')
    v = k["vyklad"]
    obsah = ""
    if k["anotace"] or k["sylabus"] or v:
        temata = odrazky(v.get("temata", ""))
        puvodni = (f'<details><summary>Původní sylabus ze SIS</summary>'
                   f'<p class="sylabus">{E(k["sylabus"])}</p></details>'
                   if k["sylabus"] else "")
        if not temata and k["sylabus"]:
            temata = f'<p class="sylabus">{E(k["sylabus"])}</p>'
            puvodni = ""
        obsah = ('<h3 class="podnadpis">O čem to je</h3>'
                 + (f'<p>{E(k["anotace"])}</p>' if k["anotace"] else "")
                 + (f'<h4 class="mini">Co se probírá</h4>{temata}' if temata else "")
                 + puvodni)

    zakonceni = ""
    if v.get("zapocet") or v.get("zkouska") or v.get("pozor") or k["podminky"]:
        sloupce = ""
        if v.get("zapocet") or v.get("zkouska"):
            sloupce = ('<div class="dvojice">'
                       + (f'<div><h4 class="mini">Na zápočet</h4>'
                          f'{odrazky(v["zapocet"])}</div>' if v.get("zapocet") else "")
                       + (f'<div><h4 class="mini">Na zkoušku</h4>'
                          f'{odrazky(v["zkouska"])}</div>' if v.get("zkouska") else "")
                       + '</div>')
        pozor = (f'<div class="pozor"><h4 class="mini">Pozor na</h4>'
                 f'{odrazky(v["pozor"])}</div>' if v.get("pozor") else "")
        delka = v.get("delka_puvodni", "")
        popisek = f" ({delka} znaků)" if delka else ""
        puvodni = (f'<details><summary>Původní znění podmínek ze SIS{popisek}</summary>'
                   f'<p class="sylabus">{E(k["podminky"])}</p></details>'
                   if k["podminky"] else "")
        if not sloupce and not pozor and k["podminky"]:
            sloupce = f'<p class="sylabus">{E(k["podminky"])}</p>'
            puvodni = ""
        zakonceni = ('<h3 class="podnadpis">Jak se to zakončuje</h3>'
                     + sloupce + pozor + puvodni)
    st = k.get("stranka") or {}
    prakticky = ""
    if st and (st.get("dochazka") or st.get("nahravky")):
        polozky = []
        d = st.get("dochazka") or "nezjisteno"
        popis, veta, trida = DOCHAZKA.get(d, DOCHAZKA["nezjisteno"])
        polozky.append(f'<div class="prakt-polozka {trida}"><h4 class="mini">Docházka</h4>'
                       f'<p><b>{E(popis)}</b> — {E(veta)}</p>'
                       + (f'<p class="doklad">„{E(st["dochazka_doklad"])}"</p>'
                          if st.get("dochazka_doklad") else "") + "</div>")
        n = st.get("nahravky") or "nezjisteno"
        if NAHRAVKY.get(n):
            polozky.append(f'<div class="prakt-polozka"><h4 class="mini">Materiály k samostudiu</h4>'
                           f'<p><b>{E(NAHRAVKY[n])}</b></p>'
                           + (f'<p class="doklad">„{E(st["nahravky_doklad"])}"</p>'
                              if st.get("nahravky_doklad") else "") + "</div>")
        if st.get("zapocet"):
            polozky.append(f'<div class="prakt-polozka"><h4 class="mini">Jak na zápočet</h4>'
                           f'<p>{E(st["zapocet"])}</p></div>')
        if st.get("samostudium"):
            polozky.append(f'<div class="prakt-polozka"><h4 class="mini">Dá se to dát bez chození?</h4>'
                           f'<p>{E(st["samostudium"])}</p></div>')
        odkazy_kurzu = "".join(
            f'<a href="{E(u)}" target="_blank" rel="noopener">{E(popisek)}</a>'
            for u, popisek in ((st.get("url_kurzu"), "stránka kurzu"),
                               (st.get("url_vyucujici"), "stránka vyučujícího"))
            if (u or "").startswith("http"))
        prakticky = ('<h3 class="podnadpis">Jak to chodí</h3>'
                     '<p class="vysvetlivka">Ze stránek kurzu a vyučujících, ne ze SIS — '
                     'proto u každého tvrzení citace zdroje.</p>'
                     f'<div class="prakticky">{"".join(polozky)}</div>'
                     + (f'<p class="odkazy">{odkazy_kurzu}</p>' if odkazy_kurzu else "")
                     + (f'<p class="sylabus">{E(st["poznamka"])}</p>' if st.get("poznamka") else ""))
    rozvrh = ('<h3 class="podnadpis">Rozvrh ZS 2026/27</h3>'
              + (f'<div class="detail-mrizka">{mrizka(k["bloky"], kurzy, jen_dny=True)}</div>'
                 if k["bloky"] else "")
              + tabulka_rozvrhu(k))
    relevance = (f'<h3 class="podnadpis">Proč to chci</h3>'
                 f'<p class="relevance">{E(k["relevance"])}</p>') if k["relevance"] else ""
    return f"""    <section class="detail" id="p-{k['kod']}" hidden>
      <a class="zpet" href="#">← zpět na přehled</a>
      <header class="detail-hlava">
        <p class="eyebrow">{E(k['kod'])} · {E(k['anglicky'])}</p>
        <h2>{E(k['nazev'])}</h2>
        <p class="detail-meta">{' · '.join(E(m) for m in meta if m.strip())}{jazyk_pruh}</p>
        {odkazy(k['kod'])}
      </header>
      {dblok(varovani + budova_pruh, "pruhy") if (varovani or budova_pruh) else ''}
      {dblok(relevance)}
      {dblok(obsah)}
      {dblok(zakonceni)}
      {dblok(prakticky)}
      {dblok(rozvrh)}
      {dblok(sekce_predmetu_anketa(k))}
      {dblok(sekce_ucitelu(k))}
      <p class="pata-detailu">Garant: {E(k['garant']) or '—'} · {E(k['pracoviste'])}
        {' · neslučitelný s ' + E(k['neslucitelnost']) if k['neslucitelnost'] else ''}</p>
    </section>"""


def slouc(bloky):
    """Paralelky ve stejny cas a ucebnu (typicky sude/liche tydny) jsou jeden slot."""
    skup = defaultdict(list)
    for b in bloky:
        skup[(b["kod"], b["typ"], b["den"], b["od"], b["do"], b["mistnost"])].append(b)
    out = []
    for (kod, typ, den, o, d, mistnost), bs in skup.items():
        prvni = dict(bs[0])
        prvni["varianty"] = len(bs)
        prvni["ucitele"] = sorted({prijmeni(x["ucitel"]) for x in bs})
        prvni["paralelky"] = [x["paralelka"] for x in bs]
        prvni["poznamky"] = sorted({x["poznamka"] for x in bs if x["poznamka"]})
        # kazda paralelka zvlast, aby se sla v rezimu stavby rozvrhu vybrat konkretne
        # (typicky sudy vs lichy tyden ve stejne ucebne a case)
        prvni["varianty_data"] = sorted(
            ({"p": x["paralelka"], "pozn": x["poznamka"], "u": prijmeni(x["ucitel"])}
             for x in bs),
            key=lambda v: (v["pozn"], v["p"]))
        out.append(prvni)
    return out


def mrizka(bloky, kurzy, ident="", jen_dny=False):
    """Mrizka jen vykresli bloky; kdo s kym koliduje a jak siroky ma byt,
    dopocita JS az podle toho, co je zrovna zapnute ve filtru."""
    if not bloky:
        return ""
    bloky = slouc(bloky)
    od = min(minuty(b["od"]) for b in bloky) // 60 * 60
    do = -(-max(minuty(b["do"]) for b in bloky) // 60) * 60
    radku = (do - od) // 15
    dny = [d for d in DNY if any(b["den"] == d for b in bloky)] if jen_dny else DNY
    bunky = ['<div class="hlavicka roh"></div>'] + \
            [f'<div class="hlavicka">{d}</div>' for d in dny]
    for h in range(od, do, 60):
        r = (h - od) // 15 + 2
        bunky.append(f'<div class="cas" style="grid-row:{r}/span 4">{h // 60}:{h % 60:02d}</div>')
        for sl in range(2, len(dny) + 2):
            bunky.append(f'<div class="pruh" style="grid-row:{r}/span 4;grid-column:{sl}"></div>')
    # zakladni rozlozeni kolidujicich bloku; u hlavni mrizky ho pak JS prepocita
    # podle toho, co je zapnute ve filtru, u detailu predmetu zustava tohle
    po_dnech = defaultdict(list)
    for b in bloky:
        if b["den"] in dny:
            po_dnech[b["den"]].append(b)
    for den_bloky in po_dnech.values():
        den_bloky.sort(key=lambda b: minuty(b["od"]))
        shluk, konec = [], -1
        def uzavri(sh):
            for i, x in enumerate(sh):
                x["_i"], x["_n"] = i, len(sh)
        for b in den_bloky:
            if shluk and minuty(b["od"]) < konec:
                shluk.append(b)
            else:
                uzavri(shluk)
                shluk, konec = [b], 0
            konec = max(konec, minuty(b["do"]))
        uzavri(shluk)
    for b in sorted(bloky, key=lambda b: (DNY.index(b["den"]) if b["den"] in DNY else 9,
                                          minuty(b["od"]))):
        if b["den"] not in dny:
            continue
        k = kurzy[b["kod"]]
        sl = dny.index(b["den"]) + 2
        r1 = (minuty(b["od"]) - od) // 15 + 2
        r2 = (minuty(b["do"]) - od) // 15 + 2
        ucitele = ", ".join(b["ucitele"])
        pozn = ", ".join(b["poznamky"])
        varianty = (f' · {b["varianty"]} varianty' if b["varianty"] > 1 else "")
        titulek = (f'{k["zkratka"]} — {b["typ"]}{varianty}, {b["den"]} {b["od"]}–{b["do"]}, '
                   f'{b["mistnost"]}, {ucitele}' + (f', {pozn}' if pozn else ""))
        bunky.append(
            f'<a class="blok sk-{k["skupina"]}{" cviceni" if b["typ"] != "přednáška" else ""}" '
            f'href="#p-{b["kod"]}" title="{E(titulek)}" data-kod="{b["kod"]}" '
            f'data-typ="{"pr" if b["typ"] == "přednáška" else "cv"}" data-den="{b["den"]}" '
            f'data-od="{minuty(b["od"])}" data-do="{minuty(b["do"])}" '
            f'data-slot="{E(b["kod"])}|{"pr" if b["typ"] == "přednáška" else "cv"}|'
            f'{E(b["den"])}|{minuty(b["od"])}|{E(b["mistnost"])}" '
            f'data-mistnost="{E(b["mistnost"])}" data-ucitel="{E(ucitele)}" '
            f'data-paralelky="{E(", ".join(b["paralelky"]))}" '
            f'data-varianty="{E(json.dumps(b["varianty_data"], ensure_ascii=False))}" '
            f'style="grid-row:{r1}/{r2};grid-column:{sl};'
            f'--i:{b.get("_i", 0)};--n:{b.get("_n", 1)}">'
            f'<b>{E(k["zkratka"])}</b>'
            f'<span class="blok-pod">{E(ucitele.split(",")[0])} · {E(b["mistnost"])}'
            f'{E(varianty)}</span></a>')
    return (f'<div class="mrizka{"" if ident else " maly"}"'
            f'{f" id={ident}" if ident else ""} '
            f'style="grid-template-columns:52px repeat({len(dny)},1fr);'
            f'grid-template-rows:auto repeat({radku},var(--ctvrt))">'
            + "".join(bunky) + "</div>")


def filtr(v_rozvrhu):
    """Prepinace nad mrizkou: typ vyuky a jednotlive predmety."""
    chipy = "".join(
        f'<label class="filtr-chip sk-{k["skupina"]}">'
        f'<input type="checkbox" data-kurz="{k["kod"]}" checked> {E(k["zkratka"])}</label>'
        for k in sorted(v_rozvrhu, key=lambda k: k["zkratka"]))
    return f"""      <div class="filtr">
        <div class="filtr-radek">
          <label class="filtr-prepinac"><input type="checkbox" id="f-pr" checked> přednášky</label>
          <label class="filtr-prepinac"><input type="checkbox" id="f-cv"> cvičení</label>
          <span class="filtr-oddel"></span>
          <button type="button" class="filtr-tlac" data-vse="1">vybrat vše</button>
          <button type="button" class="filtr-tlac" data-vse="0">zrušit výběr</button>
          <span class="filtr-stav" id="filtr-stav"></span>
        </div>
        <div class="filtr-radek chipy">{chipy}</div>
      </div>"""


# ---------------------------------------------------------------------- stavba
def main():
    kurzy = data()
    zive = [k for k in kurzy.values() if k["vrstva"] in "ABC"]
    v_rozvrhu = sorted([k for k in zive if k["bloky"]],
                       key=lambda k: (k["vrstva"], -k["kredity"]))
    bloky = [b for k in v_rozvrhu for b in k["bloky"]]
    ucitelu = sum(1 for k in zive for u in k["ucitele"].values() if u.get("uci_v_zs"))
    ucitelu_vse = sum(len(k["ucitele"]) for k in zive)
    zive_kody = {k["kod"] for k in zive}
    komentaru = sum(1 for c in nacti("anketa_komentare.csv") if c["kod"] in zive_kody)

    data_js = json.dumps([{
        "kod": k["kod"], "zkratka": k["zkratka"], "kredity": k["kredity"],
        "skupina": k["skupina"], "szz": k["szz"], "semestr": k["semestr"],
        "plan": k["plan_semestr"] if k["plan_semestr"] != "-" else "",
        "stav": k["stav_sis"], "vrstva": k["vrstva"],
        "prednasky": [{"den": b["den"], "od": minuty(b["od"]), "do": minuty(b["do"])}
                      for b in k["bloky"] if b["typ"] == "přednáška"],
    } for k in sorted(zive, key=lambda k: k["kod"])], ensure_ascii=False)
    szz_temata_js = json.dumps(
        [{"okruh": t["okruh"], "tema": t["tema"], "poradi": int(t["poradi"] or 0)}
         for t in sorted(nacti("szz_temata.csv"),
                         key=lambda t: (t["okruh"], int(t["poradi"] or 0)))],
        ensure_ascii=False)
    szz_pokryti_js = json.dumps(
        [{"okruh": r["okruh"], "tema": r["tema"], "kod": r["kod"], "sila": r["sila"]}
         for r in nacti("szz_pokryti.csv") if r["kod"] in kurzy], ensure_ascii=False)
    vyber = {r["paralelka"]: r for r in nacti("rozvrh_vyber.csv")}
    doporucene = []
    videne = set()
    for k in zive:
        for b in k["bloky"]:
            if b["paralelka"] in vyber:
                typ = "pr" if b["typ"] == "přednáška" else "cv"
                slot = f'{b["kod"]}|{typ}|{b["den"]}|{minuty(b["od"])}|{b["mistnost"]}'
                if slot not in videne:
                    videne.add(slot)
                    # dvojice, ne holy slot: doporuceni urcuje i konkretni paralelku
                    doporucene.append([slot, b["paralelka"]])
    doporuceny_js = json.dumps(doporucene, ensure_ascii=False)
    dochazka_js = json.dumps(
        {k["kod"]: {"dochazka": (k["stranka"].get("dochazka") or ""),
                    "popis": DOCHAZKA.get(k["stranka"].get("dochazka") or "", ("", "", ""))[0],
                    "trida": DOCHAZKA.get(k["stranka"].get("dochazka") or "", ("", "", ""))[2],
                    "nahravky": (k["stranka"].get("nahravky") or "")}
         for k in zive if k["stranka"]}, ensure_ascii=False)
    detaily = "\n".join(detail(k, kurzy) for k in sorted(zive, key=lambda k: k["kod"]))
    sekce_dlazdic_html = sekce_dlazdic(zive)
    filtr_dlazdic = filtr_tagu(zive)

    doc = f"""<title>Předměty magistra UI</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
{CSS}
</style>
<main>
  <div id="prehled">
    <header class="uvod">
      <p class="eyebrow">MFF UK · Informatika – Umělá inteligence · zaměření Strojové učení</p>
      <h1>Předměty a rozvrh</h1>
      <p class="perex">Kandidáti na magisterské studium od ZS 2026/27: co je v nabídce,
        kdy se to učí a co o něm říká studentská anketa. Klikni na předmět
        a rozbalí se detail — obsah, rozvrhové lístky i vyučující seřazení podle hodnocení.</p>
      <p class="souhrn"><b>{len(zive)}</b> sledovaných předmětů
        <span>{len(v_rozvrhu)} s rozvrhem v ZS</span>
        <span>{len(bloky)} rozvrhových lístků</span>
        <span>{ucitelu} vyučujících v ZS 26/27, {ucitelu_vse} v historii ankety</span>
        <span>{komentaru} připomínek z ankety</span></p>
    </header>

    <section>
      <h2 class="nadpis">Týdenní mřížka — zimní semestr 2026/27</h2>
      <p class="vysvetlivka">Mapa možností, ne rozvrh k zapsání. Vidíš <b>přednášky</b>,
        které jsou dané; cvičení jsou schovaná pod přepínačem, protože u většiny předmětů
        se stejně vybírá jedna paralelka z několika. Vypni si předměty, které neřešíš,
        a mřížka se přepočítá; paralelky ve stejný čas a učebnu (sudý a lichý týden)
        drží pohromadě jako jeden blok, ale v režimu stavby rozvrhu se mezi nimi
        klikáním přepíná. Volba se pamatuje do příště. Klik na blok
        otevře detail. Rozvrh je předběžný, SIS ho vede jako „v působnosti rozvrhové komise".</p>
      {filtr(v_rozvrhu)}
      {mrizka(bloky, kurzy, ident="mrizka")}
      <p class="legenda">
        <span class="vzorek sk-povinny"></span>povinný
        <span class="vzorek sk-profilujici"></span>profilující
        <span class="vzorek sk-rozsirujici"></span>rozšiřující
        <span class="vzorek sk-volitelny"></span>volitelný
        <span class="vzorek cviceni-vzorek"></span>světlejší = cvičení
      </p>
    </section>

    <section class="planovac" id="builder">
      <div class="planovac-hlava">
        <div>
          <h2 class="nadpis">Postavit si rozvrh</h2>
          <p class="vysvetlivka">Zapni režim a klikej nahoře v mřížce na jednotlivé hodiny —
            přednášky i cvičení zvlášť, každý blok je jedna hodina k zapsání. Dole se skládá
            tvůj týden: kredity, hodiny výuky, kolik dní musíš do školy, kolize, u kterého
            předmětu ti chybí cvičení a kam se opravdu musí chodit. Cvičení se v mřížce
            zapnou samy. Výběr zůstane uložený v prohlížeči.
            <b>Bloky označené ⇄ mají víc paralelek ve stejný čas a učebnu</b> (typicky sudý
            a lichý týden) — klik cykluje mezi nimi a teprve pak blok zase vypne. Zvolená
            paralelka se propíše do bloku, do tabulky i do výpisu a sudý s lichým se
            navzájem nepočítají jako kolize.</p>
        </div>
        <button type="button" class="rezim-tlac" id="rezim-rozvrh">Zapnout stavbu rozvrhu</button>
      </div>
      <div id="builder-telo" hidden>
        <div class="planovac-lista">
          <label class="filtr-prepinac"><input type="checkbox" id="f-jen-moje">
            v mřížce ukázat jen můj rozvrh</label>
          <div class="ulozene">
            <button type="button" class="lista-tlac hlavni" id="z-repa-rozvrh">Načíst doporučený rozvrh</button>
            <button type="button" class="lista-tlac" id="z-planu">Předvyplnit z plánu (ZS 26/27)</button>
            <button type="button" class="lista-tlac" id="vsechny-prednasky">Přidat všechny přednášky</button>
            <button type="button" class="lista-tlac zrus" id="vycisti-rozvrh">Vyprázdnit rozvrh</button>
          </div>
        </div>
        <p class="lista-hlaska" id="hlaska-rozvrh" role="status"></p>
        <div class="souhrn-pruh" id="rozvrh-bilance"></div>
        <div id="rozvrh-telo"></div>
      </div>
    </section>

    <section class="planovac" id="planovac">
      <div class="planovac-hlava">
        <div>
          <h2 class="nadpis">Zkusit si plán</h2>
          <p class="vysvetlivka">Zapni režim, klikáním na dlaždice skládej svůj výběr
            a rozhoď ho do semestrů. Stránka průběžně počítá kredity po skupinách,
            hlídá minima, pokrytí státnicových okruhů i kolize přednášek v zimním
            semestru. Výběr zůstane uložený v prohlížeči.</p>
        </div>
        <button type="button" class="rezim-tlac" id="rezim">Zapnout plánovací režim</button>
      </div>
      <div id="planovac-telo" hidden>
        <div class="planovac-lista">
          <div class="usek-volba" role="group" aria-label="Rozložení ročníku">
            <span class="lista-popis">Rozložení ročníku:</span>
            <label><input type="radio" name="usek" value="bez" checked> žádné (2+ roky standardně)</label>
            <label><input type="radio" name="usek" value="usek2"> rozložený 2. úsek</label>
            <label><input type="radio" name="usek" value="usek1"> rozložený 1. úsek</label>
          </div>
          <div class="ulozene">
            <button type="button" class="lista-tlac hlavni" id="z-repa">Načíst plán z repozitáře</button>
            <span class="filtr-oddel"></span>
            <input type="text" id="nazev-verze" placeholder="název verze"
                   aria-label="Název nové verze plánu">
            <button type="button" class="lista-tlac" id="uloz-verzi">Uložit verzi</button>
            <select id="verze" aria-label="Uložené verze plánu"></select>
            <button type="button" class="lista-tlac" id="nacti-verzi">Načíst</button>
            <button type="button" class="lista-tlac" id="smaz-verzi">Smazat</button>
            <button type="button" class="lista-tlac zrus" id="vycisti">Vyprázdnit plán</button>
          </div>
        </div>
        <p class="lista-hlaska" id="hlaska" role="status"></p>
        <p class="vysvetlivka">Mazací tlačítka se ptají dvojklikem: první klik položí otázku,
          druhý ji potvrdí. Okénka <code>confirm()</code> jsou uvnitř publikované stránky
          umlčená, proto to takhle.</p>
        <div class="souhrn-pruh" id="bilance"></div>
        <div class="planovac-mriz">
          <div><h3 class="podnadpis">Státnicové okruhy</h3><div id="szz-stav"></div></div>
          <div><h3 class="podnadpis">Rozvržení do semestrů</h3><div id="semestry"></div></div>
        </div>
        <details><summary>Vzít výběr do repozitáře nebo ho odsud dostat pryč</summary>
          <p class="vysvetlivka">Řádky <code>kod,plan_semestr</code> se dají vložit do
            <code>data/predmety.csv</code> — nebo je pošli Claudovi, ať plán zapíše.
            Do stejného pole můžeš text vložit zpátky a plán tím obnovit.</p>
          <textarea id="export" rows="8" spellcheck="false"></textarea>
          <button type="button" class="lista-tlac" id="nacti-text">Načíst z textu</button></details>
      </div>
    </section>

    <section>
      <h2 class="nadpis">Předměty podle skupin</h2>
      <p class="vysvetlivka">Rozdělené tak, jak se počítají kredity: povinné, profilující
        (min. 38 kr), rozšiřující (min. 15 kr) a volitelné. Na dlaždici je semestr výuky,
        oblasti předmětu a hodnocení předmětu v anketě; konkrétní hodiny najdeš
        v mřížce nahoře a v detailu. Filtruj podle oblasti nebo hledáním.</p>
      {filtr_dlazdic}
      <div id="dlazdice-vse">
{sekce_dlazdic_html}
      </div>
      <p class="prazdno" id="dlazdice-nic" hidden>Filtru nic neodpovídá.</p>
    </section>

    <footer>
      <p>Data ze SIS: předměty a anotace, veřejný CSV export rozvrhu ZS {SKR}/27
        a veřejné výsledky studentské ankety. Staženo skripty v
        <code>~/mff/studijni-plan/tools/</code>, stránku staví <code>tools/artifact.py</code>.</p>
      <p>Studijní plán pro 2026/2027 zatím nevyšel — vše vychází z verze 2025/2026
        a před zápisem se musí překontrolovat.</p>
    </footer>
  </div>

{detaily}
</main>
<script>
const KURZY = {data_js};
const SZZ_DOPORUCENE = {json.dumps(SZZ_DOPORUCENE)};
const SZZ_NAZVY = {json.dumps(SZZ, ensure_ascii=False)};
const SZZ_TEMATA = {szz_temata_js};
const SZZ_POKRYTI = {szz_pokryti_js};
const DOCHAZKA_DATA = {dochazka_js};
const DOPORUCENY_ROZVRH = {doporuceny_js};
const MINIMA = {json.dumps(MINIMA)};
{JS}
{PLANOVAC}
{BUILDER}
</script>
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(doc)
    print(f"-> {OUT} ({len(zive)} predmetu, {len(bloky)} bloku, {komentaru} komentaru, "
          f"{len(doc)//1024} kB)")


JS = r"""
const prehled = document.getElementById('prehled');
const mrizka = document.getElementById('mrizka');
const bloky = mrizka ? Array.from(mrizka.querySelectorAll('.blok')) : [];
const kurzyBox = Array.from(document.querySelectorAll('[data-kurz]'));
const KLIC = 'studijni-plan-filtr-v1';

function nactiStav() {
  try { return JSON.parse(localStorage.getItem(KLIC)); } catch (e) { return null; }
}
function ulozStav(s) {
  try { localStorage.setItem(KLIC, JSON.stringify(s)); } catch (e) { /* soukrome okno */ }
}
let filtrDoplnek = function () { return false; };   // rezim stavby rozvrhu si ho prepise
function rozloz() {
  const prednasky = document.getElementById('f-pr').checked;
  const cviceni = document.getElementById('f-cv').checked;
  const vypnute = kurzyBox.filter(function (c) { return !c.checked; })
                          .map(function (c) { return c.dataset.kurz; });
  const vyp = new Set(vypnute);
  bloky.forEach(function (b) {
    const typOk = b.dataset.typ === 'pr' ? prednasky : cviceni;
    b.hidden = vyp.has(b.dataset.kod) || !typOk || filtrDoplnek(b);
  });
  // sirku a odsazeni kolidujicich bloku pocitam az z toho, co je videt
  const dny = {};
  bloky.forEach(function (b) {
    if (b.hidden) { return; }
    (dny[b.dataset.den] = dny[b.dataset.den] || []).push(b);
  });
  Object.keys(dny).forEach(function (den) {
    const list = dny[den].sort(function (a, b) { return a.dataset.od - b.dataset.od; });
    let shluk = [], konec = -1;
    const uzavri = function () {
      shluk.forEach(function (x, i) {
        x.style.setProperty('--i', i);
        x.style.setProperty('--n', shluk.length);
      });
    };
    list.forEach(function (b) {
      if (shluk.length && +b.dataset.od < konec) { shluk.push(b); }
      else { uzavri(); shluk = [b]; konec = 0; }
      konec = Math.max(konec, +b.dataset.do);
    });
    uzavri();
  });
  const videt = bloky.filter(function (b) { return !b.hidden; }).length;
  const stav = document.getElementById('filtr-stav');
  if (stav) {
    stav.textContent = videt === bloky.length
      ? bloky.length + ' bloků'
      : videt + ' z ' + bloky.length + ' bloků';
  }
  ulozStav({ pr: prednasky, cv: cviceni, vyp: vypnute });
}
if (mrizka) {
  const ulozeny = nactiStav();
  if (ulozeny) {
    document.getElementById('f-pr').checked = ulozeny.pr !== false;
    document.getElementById('f-cv').checked = ulozeny.cv === true;
    const vyp = new Set(ulozeny.vyp || []);
    kurzyBox.forEach(function (c) { c.checked = !vyp.has(c.dataset.kurz); });
  }
  document.querySelectorAll('.filtr input').forEach(function (c) {
    c.addEventListener('change', rozloz);
  });
  document.querySelectorAll('.filtr-tlac').forEach(function (b) {
    b.addEventListener('click', function () {
      kurzyBox.forEach(function (c) { c.checked = b.dataset.vse === '1'; });
      rozloz();
    });
  });
  rozloz();
}
// ------------------------------------------------ filtrovani dlazdic podle oblasti
const dlazdiceVse = Array.from(document.querySelectorAll('#dlazdice-vse .dlazdice'));
const KLIC_TAGY = 'studijni-plan-tagy-v1';
let aktivniTagy = new Set();
let aktivniZam = new Set();
function ulozTagy() {
  try {
    localStorage.setItem(KLIC_TAGY, JSON.stringify({
      tagy: Array.from(aktivniTagy),
      zam: Array.from(aktivniZam),
      hledani: document.getElementById('hledani').value,
      zima: document.getElementById('f-zima').checked,
      jadro: document.getElementById('f-jadro').checked }));
  } catch (e) { /* soukrome okno */ }
}
function filtrujDlazdice() {
  const q = document.getElementById('hledani').value.trim().toLowerCase();
  const jenZima = document.getElementById('f-zima').checked;
  const jenJadro = document.getElementById('f-jadro').checked;
  let videt = 0;
  dlazdiceVse.forEach(function (d) {
    const tagy = (d.dataset.tagy || '').split(' ').filter(Boolean);
    const okTag = !aktivniTagy.size || tagy.some(function (t) { return aktivniTagy.has(t); });
    const okQ = !q || (d.dataset.hledat || '').indexOf(q) >= 0;
    const okZima = !jenZima || d.dataset.semestr === 'zimní' || d.dataset.semestr === 'oba';
    const okJadro = !jenJadro || d.dataset.vrstva !== 'C';
    // 'vse' = predmet spolecny celemu programu, ten zustava videt vzdy
    const zam = (d.dataset.zamereni || 'vse').split(' ').filter(Boolean);
    const okZam = !aktivniZam.size || zam.indexOf('vse') >= 0
      || zam.some(function (z) { return aktivniZam.has(z); });
    const ok = okTag && okQ && okZima && okJadro && okZam;
    d.hidden = !ok;
    if (ok) { videt++; }
  });
  document.querySelectorAll('.skupina-sekce').forEach(function (sek) {
    sek.hidden = !sek.querySelector('.dlazdice:not([hidden])');
  });
  document.getElementById('dlazdice-nic').hidden = videt > 0;
  document.querySelectorAll('.tag-tlac').forEach(function (b) {
    b.classList.toggle('aktivni', aktivniTagy.has(b.dataset.tag));
  });
  document.querySelectorAll('.zam-tlac').forEach(function (b) {
    b.classList.toggle('aktivni', aktivniZam.has(b.dataset.zam));
  });
  const stav = document.getElementById('dlazdice-stav');
  stav.textContent = videt === dlazdiceVse.length
    ? dlazdiceVse.length + ' předmětů'
    : videt + ' z ' + dlazdiceVse.length + ' předmětů';
  ulozTagy();
}
if (document.getElementById('hledani')) {
  try {
    const ul = JSON.parse(localStorage.getItem(KLIC_TAGY));
    if (ul) {
      aktivniTagy = new Set(ul.tagy || []);
      aktivniZam = new Set(ul.zam || []);
      document.getElementById('hledani').value = ul.hledani || '';
      document.getElementById('f-zima').checked = ul.zima === true;
      document.getElementById('f-jadro').checked = ul.jadro === true;
    }
  } catch (e) { /* nic */ }
  document.querySelectorAll('.zam-tlac').forEach(function (b) {
    b.addEventListener('click', function () {
      if (aktivniZam.has(b.dataset.zam)) { aktivniZam.delete(b.dataset.zam); }
      else { aktivniZam.add(b.dataset.zam); }
      filtrujDlazdice();
    });
  });
  document.querySelectorAll('.tag-tlac').forEach(function (b) {
    b.addEventListener('click', function () {
      if (aktivniTagy.has(b.dataset.tag)) { aktivniTagy.delete(b.dataset.tag); }
      else { aktivniTagy.add(b.dataset.tag); }
      filtrujDlazdice();
    });
  });
  document.getElementById('hledani').addEventListener('input', filtrujDlazdice);
  document.getElementById('f-zima').addEventListener('change', filtrujDlazdice);
  document.getElementById('f-jadro').addEventListener('change', filtrujDlazdice);
  document.getElementById('tagy-vse').addEventListener('click', function () {
    aktivniTagy.clear();
    aktivniZam.clear();
    document.getElementById('hledani').value = '';
    document.getElementById('f-zima').checked = false;
    document.getElementById('f-jadro').checked = false;
    filtrujDlazdice();
  });
  filtrujDlazdice();
}
function zobraz() {
  const id = location.hash.slice(1);
  const cil = id ? document.getElementById(id) : null;
  document.querySelectorAll('.detail').forEach(function (d) { d.hidden = d !== cil; });
  prehled.hidden = !!cil;
  if (cil) { cil.focus({ preventScroll: true }); }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', zobraz);
zobraz();
"""

PLANOVAC = r"""
// ---------------------------------------------------------------- planovaci rezim
const SEMESTRY = [["ZS1", "ZS 26/27"], ["LS1", "LS 27"], ["ZS2", "ZS 27/28"],
                  ["LS2", "LS 28"], ["ZS3", "ZS 28/29"], ["LS3", "LS 29"]];
const SKUPINY_POR = [["povinny", "povinné"], ["profilujici", "profilující"],
                     ["rozsirujici", "rozšiřující"], ["volitelny", "volitelné"]];
const KLIC_PLAN = 'studijni-plan-vyber-v1';
const kurzPodleKodu = {};
KURZY.forEach(function (k) { kurzPodleKodu[k.kod] = k; });
const KLIC_VERZE = 'studijni-plan-verze-v1';
let plan = {};          // kod -> semestr ('' = zatím nezařazeno)
let usek = 'bez';       // bez | usek1 | usek2
let rezimZapnut = false;

// confirm() a prompt() jsou v sandboxu artifactu umlcene (vrati se false/null a nic se
// nestane), takze se potvrzuje dvojklikem na tlacitko a hlasi se do prouzku vedle.
function hlaska(kam, text) {
  const h = document.getElementById(kam);
  if (!h) { return; }
  h.textContent = text;
  clearTimeout(h._t);
  h._t = setTimeout(function () { h.textContent = ''; }, 5000);
}
function potvrd(btn, otazka, akce) {
  if (btn.dataset.ceka === '1') {
    clearTimeout(btn._t);
    btn.dataset.ceka = '0';
    btn.textContent = btn.dataset.puvodni;
    btn.classList.remove('ceka');
    akce();
    return;
  }
  btn.dataset.puvodni = btn.dataset.puvodni || btn.textContent;
  btn.dataset.ceka = '1';
  btn.textContent = otazka;
  btn.classList.add('ceka');
  clearTimeout(btn._t);
  btn._t = setTimeout(function () {
    btn.dataset.ceka = '0';
    btn.textContent = btn.dataset.puvodni;
    btn.classList.remove('ceka');
  }, 5000);
}
function nactiPlan() {
  try {
    const d = JSON.parse(localStorage.getItem(KLIC_PLAN));
    if (!d) { return; }
    if (d.vyber) { plan = d.vyber; usek = d.usek || 'bez'; }
    else { plan = d; }                       // starší podoba: jen mapa kód → semestr
  } catch (e) { /* soukromé okno nebo poškozený zápis */ }
}
function ulozPlan() {
  try {
    localStorage.setItem(KLIC_PLAN, JSON.stringify({ vyber: plan, usek: usek }));
  } catch (e) { /* nic */ }
}
function nactiVerze() {
  try { return JSON.parse(localStorage.getItem(KLIC_VERZE)) || {}; } catch (e) { return {}; }
}
function ulozVerze(v) {
  try { localStorage.setItem(KLIC_VERZE, JSON.stringify(v)); } catch (e) { /* nic */ }
}
function vykresliVerze() {
  const v = nactiVerze();
  const sel = document.getElementById('verze');
  const jmena = Object.keys(v).sort();
  sel.innerHTML = jmena.length
    ? jmena.map(function (j) { return '<option>' + j + '</option>'; }).join('')
    : '<option value="">(žádná uložená verze)</option>';
}
function mozneSemestry(k) {
  if (k.semestr === 'zimní') { return SEMESTRY.filter(function (s) { return s[0][0] === 'Z'; }); }
  if (k.semestr === 'letní') { return SEMESTRY.filter(function (s) { return s[0][0] === 'L'; }); }
  return SEMESTRY;
}
function vykresliBilanci() {
  const vybrane = Object.keys(plan);
  const soucty = {};
  SKUPINY_POR.forEach(function (s) { soucty[s[0]] = 0; });
  let celkem = 0;
  vybrane.forEach(function (kod) {
    const k = kurzPodleKodu[kod];
    soucty[k.skupina] += k.kredity;
    celkem += k.kredity;
  });
  let html = '<div class="bil-polozka celkem"><b>' + celkem + '</b><span>kreditů z 120</span></div>';
  SKUPINY_POR.forEach(function (s) {
    const kr = soucty[s[0]], min = MINIMA[s[0]];
    const stav = min === 0 ? 'neutral' : (kr >= min ? 'ok' : 'chybi');
    html += '<div class="bil-polozka sk-' + s[0] + ' ' + stav + '"><b>' + kr + '</b>'
          + '<span>' + s[1] + (min ? ' · min. ' + min : '') + '</span></div>';
  });
  const nevyucovane = vybrane.filter(function (kod) { return kurzPodleKodu[kod].stav === 'nevyučován'; });
  if (nevyucovane.length) {
    html += '<div class="bil-polozka chybi"><b>!</b><span>' + nevyucovane.length
          + '× nevyučovaný předmět</span></div>';
  }
  document.getElementById('bilance').innerHTML = html;
}
function zk(kod) {
  return (kurzPodleKodu[kod] && kurzPodleKodu[kod].zkratka) || kod;
}
function szzPodleDoporucenych(okruh, nazev) {
  const dop = SZZ_DOPORUCENE[okruh] || [];
  const mam = dop.filter(function (k) { return plan.hasOwnProperty(k); });
  const chybi = dop.filter(function (k) { return !plan.hasOwnProperty(k) && kurzPodleKodu[k]; });
  const stav = mam.length >= 2 ? 'ok' : (mam.length === 1 ? 'castecne' : 'chybi');
  return '<div class="szz-radek ' + stav + '"><b>' + nazev + '</b>'
       + '<span>' + mam.length + ' ze ' + dop.length + ' doporučených</span>'
       + (chybi.length ? '<span class="tlumene">chybí: ' + chybi.map(function (k) {
           return zk(k) + (kurzPodleKodu[k].stav === 'nevyučován' ? ' (neučí se)' : '');
         }).join(', ') + '</span>' : '')
       + '</div>';
}
let szzOtevrene = new Set();          // ktere okruhy si necha Jakub rozbalene
function vykresliSzz() {
  let html = '';
  let mameTemata = false;
  ['SU', 'NS', 'DZ'].forEach(function (okruh) {
    const nazev = SZZ_NAZVY[okruh];
    const temata = SZZ_TEMATA.filter(function (t) { return t.okruh === okruh; });
    if (!temata.length) { html += szzPodleDoporucenych(okruh, nazev); return; }
    mameTemata = true;
    let plne = 0, castecne = 0, radky = '';
    temata.forEach(function (t) {
      const vse = SZZ_POKRYTI.filter(function (p) {
        return p.okruh === okruh && p.tema === t.tema; });
      const mam = vse.filter(function (p) { return plan.hasOwnProperty(p.kod); });
      const hlavni = mam.filter(function (p) { return p.sila === 'hlavni'; });
      const stav = hlavni.length ? 'ok' : (mam.length ? 'castecne' : 'chybi');
      if (stav === 'ok') { plne++; } else if (stav === 'castecne') { castecne++; }
      const kdo = mam.slice().sort(function (a, b) {
          return (a.sila === 'hlavni' ? 0 : 1) - (b.sila === 'hlavni' ? 0 : 1); })
        .map(function (p) { return zk(p.kod) + (p.sila === 'hlavni' ? '' : ' · ' + p.sila); });
      const pomoc = vse.filter(function (p) { return !plan.hasOwnProperty(p.kod); })
        .sort(function (a, b) {
          return (a.sila === 'hlavni' ? 0 : 1) - (b.sila === 'hlavni' ? 0 : 1); });
      radky += '<li class="' + stav + '"><b>' + t.tema + '</b>'
             + (kdo.length ? '<span>' + kdo.join(', ') + '</span>' : '')
             + (stav !== 'ok' && pomoc.length
                 ? '<span class="tlumene">přidat by pomohlo: '
                   + pomoc.slice(0, 3).map(function (p) {
                       return zk(p.kod) + (p.sila === 'hlavni' ? '' : ' · ' + p.sila)
                            + (kurzPodleKodu[p.kod] && kurzPodleKodu[p.kod].stav === 'nevyučován'
                               ? ' (neučí se)' : ''); }).join(', ') + '</span>'
                 : '')
             + (stav === 'chybi' && !pomoc.length
                 ? '<span class="tlumene">nepokrývá žádný sledovaný předmět</span>' : '')
             + '</li>';
    });
    const stavO = plne === temata.length ? 'ok' : (plne + castecne ? 'castecne' : 'chybi');
    const chybi = temata.length - plne - castecne;
    html += '<details class="szz-radek ' + stavO + '"'
          + (szzOtevrene.has(okruh) ? ' open' : '') + ' data-okruh="' + okruh + '">'
          + '<summary><b>' + nazev + '</b>'
          + '<span>' + plne + ' z ' + temata.length + ' témat naplno'
          + (castecne ? ', ' + castecne + ' částečně' : '')
          + (chybi ? ', ' + chybi + ' bez pokrytí' : '') + '</span></summary>'
          + '<ul class="szz-temata">' + radky + '</ul></details>';
  });
  html += '<p class="vysvetlivka">' + (mameTemata
        ? 'Témata jsou rozepsaná z požadavků ke státnicím zaměření Strojové učení; '
          + 'pokrytí se posuzuje proti sylabům předmětů v SIS, u každé dvojice je '
          + 'v repozitáři doslovná citace ze sylabu (data/szz_pokryti.csv). '
          + '„Naplno" = některý předmět z výběru tomu tématu věnuje podstatnou část sylabu.'
        : 'Seznam doporučených předmětů je ze studijního plánu; formálně tě k ničemu '
          + 'nezavazuje, ale okruh, ze kterého nemáš nic, se zkouší špatně.') + '</p>';
  const box = document.getElementById('szz-stav');
  box.innerHTML = html;
  box.querySelectorAll('details[data-okruh]').forEach(function (d) {
    d.addEventListener('toggle', function () {
      if (d.open) { szzOtevrene.add(d.dataset.okruh); } else { szzOtevrene.delete(d.dataset.okruh); }
    });
  });
}
function vykresliSemestry() {
  const vybrane = Object.keys(plan).sort(function (a, b) {
    return kurzPodleKodu[b].kredity - kurzPodleKodu[a].kredity; });
  if (!vybrane.length) {
    document.getElementById('semestry').innerHTML =
      '<p class="prazdno">Zatím nic nevybráno — klikni na dlaždici předmětu níž.</p>';
    document.getElementById('export').value = '';
    return;
  }
  // rozdeleni do skupin: nezarazene napred, pak semestr po semestru
  const podle = {};
  SEMESTRY.forEach(function (s) { podle[s[0]] = []; });
  const bezSemestru = [];
  vybrane.forEach(function (kod) {
    if (plan[kod] && podle[plan[kod]]) { podle[plan[kod]].push(kod); }
    else { bezSemestru.push(kod); }
  });
  const nezarazeno = bezSemestru.length;
  const kr = function (kody) {
    return kody.reduce(function (a, k) { return a + kurzPodleKodu[k].kredity; }, 0); };

  const radek = function (kod) {
    const k = kurzPodleKodu[kod];
    const tlacitka = mozneSemestry(k).map(function (s) {
      const je = plan[kod] === s[0];
      return '<button type="button" class="sem-tlac' + (je ? ' aktivni' : '')
           + '" data-kod="' + kod + '" data-sem="' + s[0] + '" title="'
           + (je ? 'zpět mezi nezařazené' : 'zařadit do ' + s[1]) + '">' + s[1] + '</button>';
    }).join('');
    return '<tr><td><b>' + k.zkratka + '</b> <a class="kod-odkaz" href="#p-' + kod
         + '" title="otevřít detail předmětu">' + k.kod + '</a></td>'
         + '<td class="c">' + k.kredity + '</td><td class="sem-volba">' + tlacitka
         + '<button type="button" class="sem-tlac zrus" data-kod="' + kod
         + '" data-akce="odeber" title="odebrat předmět z plánu">×</button></td></tr>';
  };

  let html = '<div class="tab-obal"><table class="tab-semestry"><thead><tr><th>Předmět</th>'
           + '<th class="c">Kr</th><th>Kam</th></tr></thead>';
  const skupiny = [['', 'Zatím nezařazeno', bezSemestru]].concat(
    SEMESTRY.map(function (s) { return [s[0], s[1], podle[s[0]]]; }));
  skupiny.forEach(function (g) {
    if (g[0] === '' && !g[2].length) { return; }          // prazdna skupina jen u semestru
    const soucet = kr(g[2]);
    const popis = g[0] === '' ? g[2].length + '× bez semestru' : soucet + ' kr';
    html += '<tbody class="sem-skupina' + (g[0] === '' ? ' nezarazene' : '')
          + (soucet > 33 ? ' hodne' : '') + '">'
          + '<tr class="sem-hlava"><th colspan="3"><div class="sem-hlava-obal">'
          + '<span>' + g[1] + '</span>'
          + '<span class="sem-hlava-kr">' + popis + '</span></div></th></tr>'
          + (g[2].length ? g[2].map(radek).join('')
             : '<tr class="sem-volna"><td colspan="3">volný semestr</td></tr>')
          + '</tbody>';
  });
  html += '</table></div>';

  const rok1 = kr(podle.ZS1) + kr(podle.LS1);
  const rok2 = kr(podle.ZS2) + kr(podle.LS2);
  const rok3 = kr(podle.ZS3) + kr(podle.LS3);
  const celkem = rok1 + rok2 + rok3;
  const kontrola = [];
  if (usek === 'bez') {
    kontrola.push([rok1 >= 45, 'Kontrola po 1. roce: ' + rok1
      + ' kr (minimum 45; s uznáním 6 kr z bakaláře stačí odstudovat 39)']);
    kontrola.push([rok1 + rok2 >= 90, 'Kontrola po 2. roce: ' + (rok1 + rok2)
      + ' kr (minimum 90)']);
  } else if (usek === 'usek2') {
    kontrola.push([rok1 >= 45, 'Kontrola po 1. roce: ' + rok1
      + ' kr (minimum 45; s uznáním 6 kr z bakaláře stačí odstudovat 39)']);
    kontrola.push([true, 'Po 2. roce se nekontroluje — druhý úsek je rozložený přes 2. a 3. rok']);
  } else {
    kontrola.push([true, 'Po 1. roce se nekontroluje — první úsek je rozložený přes 1. a 2. rok']);
    kontrola.push([rok1 + rok2 >= 45, 'Kontrola po 2. roce: ' + (rok1 + rok2)
      + ' kr (minimum 45 za celý rozložený 1. úsek)']);

  }
  kontrola.push([celkem >= 120, 'Celkem rozvrženo ' + celkem + ' kr (na SZZ potřeba 120)']);
  kontrola.push([nezarazeno === 0, nezarazeno + ' vybraných předmětů zatím nemá semestr']);
  html += '<ul class="kontrola">' + kontrola.map(function (c) {
    return '<li class="' + (c[0] ? 'ok' : 'chybi') + '">' + (c[0] ? '✓ ' : '✗ ') + c[1] + '</li>';
  }).join('') + '</ul>';
  if (usek === 'usek1') {
    html += '<p class="vysvetlivka">Pozor na past rozloženého prvního úseku: třetí rok '
          + 'je celý druhý úsek a musí studium dotáhnout na 120 kreditů — co nestihneš '
          + 'do konce druhého roku, spadne všechno do něj.</p>';
  }
  html += '<p class="vysvetlivka">Roky: 1. rok = ZS 26/27 + LS 27 atd. Rozložení ročníku '
        + 'schvaluje studijní proděkan, není na něj nárok. Tři roky jsou pořád v bezplatné '
        + 'době studia (standardní doba 2 roky + 1 rok), čtvrtý už ne. Kolize hodin se tady '
        + 'neřeší — na to je režim stavby rozvrhu.</p>';
  document.getElementById('semestry').innerHTML = html;
  document.getElementById('export').value = 'kod,plan_semestr\n'
    + vybrane.map(function (k) { return k + ',' + (plan[k] || ''); }).join('\n');
}
function vykresliNadpisySkupin() {
  document.querySelectorAll('.skupina-vybrano').forEach(function (el) {
    if (!rezimZapnut) { el.textContent = ''; el.className = 'skupina-vybrano'; return; }
    const slug = el.dataset.skupina;
    const min = +el.dataset.min || 0;
    let kr = 0, pocet = 0;
    Object.keys(plan).forEach(function (kod) {
      const k = kurzPodleKodu[kod];
      if (k && k.skupina === slug) { kr += k.kredity; pocet++; }
    });
    const slovo = pocet === 1 ? 'předmět' : (pocet < 5 ? 'předměty' : 'předmětů');
    el.textContent = 'vybráno ' + (min ? kr + ' z ' + min + ' kr' : kr + ' kr')
                   + ' · ' + pocet + ' ' + slovo;
    el.className = 'skupina-vybrano' + (min ? (kr >= min ? ' ok' : ' chybi') : ' neutral');
  });
}
function prekresli() {
  vykresliNadpisySkupin();
  document.querySelectorAll('.dlazdice').forEach(function (d) {
    const je = plan.hasOwnProperty(d.dataset.kod);
    d.classList.toggle('vybrana', je);
    d.setAttribute('aria-pressed', je ? 'true' : 'false');
  });
  vykresliBilanci(); vykresliSzz(); vykresliSemestry(); ulozPlan();
  if (stavimZapnut) { vykresliRozvrh(); }   // kontroly rozvrhu se odkazuji na plan
}
function prepniKurz(kod) {
  if (plan.hasOwnProperty(kod)) { delete plan[kod]; } else { plan[kod] = ''; }
  prekresli();
}
document.querySelectorAll('.dlazdice').forEach(function (d) {
  d.addEventListener('click', function (e) {
    if (e.target.closest('a')) { return; }     // nazev i sipka vedou na detail vzdy
    if (!rezimZapnut) { location.hash = '#p-' + d.dataset.kod; return; }
    e.preventDefault();
    prepniKurz(d.dataset.kod);
  });
  d.addEventListener('keydown', function (e) {
    if (rezimZapnut && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault(); prepniKurz(d.dataset.kod);
    }
  });
});
document.getElementById('semestry').addEventListener('click', function (e) {
  const t = e.target.closest('.sem-tlac');
  if (!t) { return; }
  const kod = t.dataset.kod;
  if (t.dataset.akce === 'odeber') { delete plan[kod]; prekresli(); return; }
  // druhé kliknutí na už zvolený semestr vrátí předmět mezi nezařazené
  plan[kod] = plan[kod] === t.dataset.sem ? '' : t.dataset.sem;
  prekresli();
});
document.getElementById('rezim').addEventListener('click', function () {
  rezimZapnut = !rezimZapnut;
  document.body.classList.toggle('planuji', rezimZapnut);
  document.getElementById('planovac-telo').hidden = !rezimZapnut;
  this.textContent = rezimZapnut ? 'Vypnout plánovací režim' : 'Zapnout plánovací režim';
  prekresli();
});
document.querySelectorAll('input[name="usek"]').forEach(function (r) {
  r.addEventListener('change', function () { usek = r.value; prekresli(); });
});
document.getElementById('uloz-verzi').addEventListener('click', function () {
  const pole = document.getElementById('nazev-verze');
  const jmeno = (pole.value || '').trim()
             || ('plán ' + new Date().toLocaleDateString('cs-CZ'));
  const v = nactiVerze();
  v[jmeno] = { vyber: plan, usek: usek, rozvrh: Object.assign({}, rozvrh || {}) };
  ulozVerze(v); vykresliVerze();
  document.getElementById('verze').value = jmeno;
  pole.value = '';
  hlaska('hlaska', 'Uloženo jako „' + jmeno + '".');
});
document.getElementById('nacti-verzi').addEventListener('click', function () {
  const jmeno = document.getElementById('verze').value;
  const v = nactiVerze();
  if (!jmeno || !v[jmeno]) { return; }
  plan = Object.assign({}, v[jmeno].vyber);
  usek = v[jmeno].usek || 'bez';
  document.querySelector('input[name="usek"][value="' + usek + '"]').checked = true;
  rozvrh = Object.assign({}, v[jmeno].rozvrh || {});
  ulozRozvrh();
  prekresli();
  vykresliRozvrh(); rozloz();
  hlaska('hlaska', 'Načtena verze „' + jmeno + '".');
});
document.getElementById('smaz-verzi').addEventListener('click', function () {
  const jmeno = document.getElementById('verze').value;
  const v = nactiVerze();
  if (!jmeno || !v[jmeno]) { hlaska('hlaska', 'Není vybraná žádná uložená verze.'); return; }
  potvrd(this, 'Opravdu smazat „' + jmeno + '"?', function () {
    const vv = nactiVerze();
    delete vv[jmeno]; ulozVerze(vv); vykresliVerze();
    hlaska('hlaska', 'Verze „' + jmeno + '" smazána.');
  });
});
document.getElementById('vycisti').addEventListener('click', function () {
  if (!Object.keys(plan).length) { hlaska('hlaska', 'Plán je už prázdný.'); return; }
  potvrd(this, 'Opravdu vyprázdnit?', function () {
    plan = {}; prekresli();
    hlaska('hlaska', 'Plán vyprázdněn, uložené verze zůstaly.');
  });
});
document.getElementById('z-repa').addEventListener('click', function () {
  const novy = {};
  KURZY.forEach(function (k) { if (k.plan) { novy[k.kod] = k.plan; } });
  if (!Object.keys(novy).length) {
    hlaska('hlaska', 'V repozitáři zatím žádný plán není.'); return;
  }
  plan = novy;
  usek = 'usek2';                       // plán v repu je postavený na rozložený 2. úsek
  const p = document.querySelector('input[name="usek"][value="usek2"]');
  if (p) { p.checked = true; }
  prekresli();
  hlaska('hlaska', 'Načten plán z repozitáře: ' + Object.keys(novy).length
       + ' předmětů, rozložený 2. úsek.');
});
document.getElementById('nacti-text').addEventListener('click', function () {
  const radky = document.getElementById('export').value.split('\n');
  const novy = {};
  radky.forEach(function (r) {
    const c = r.split(',').map(function (x) { return x.trim(); });
    if (c[0] && c[0] !== 'kod' && kurzPodleKodu[c[0]]) { novy[c[0]] = c[1] || ''; }
  });
  if (!Object.keys(novy).length) {
    hlaska('hlaska', 'V textu jsem nenašel žádný známý kód předmětu.'); return;
  }
  plan = novy; prekresli();
  hlaska('hlaska', 'Načteno ' + Object.keys(novy).length + ' předmětů z textu.');
});
nactiPlan();
vykresliVerze();
const prepinac = document.querySelector('input[name="usek"][value="' + usek + '"]');
if (prepinac) { prepinac.checked = true; }
if (Object.keys(plan).length) { document.getElementById('rezim').click(); }
"""


BUILDER = r"""
// ------------------------------------------------------------ rezim stavby rozvrhu ZS
// Zamerne var, ne let: PLANOVAC bezi driv a saha na `rozvrh` i `stavimZapnut`,
// s let by narazil do temporal dead zone.
var KLIC_ROZVRH = 'studijni-plan-rozvrh-v1';
var rozvrh = {};
var stavimZapnut = false;
var jenMoje = false;
var DNY_POR = ['Po', 'Út', 'St', 'Čt', 'Pá'];
var slotBloky = mrizka ? Array.from(mrizka.querySelectorAll('.blok[data-slot]')) : [];

function varianty(b) {
  try { return JSON.parse(b.dataset.varianty || '[]'); } catch (e) { return []; }
}
function slotData(b) {
  return { slot: b.dataset.slot, kod: b.dataset.kod, typ: b.dataset.typ, den: b.dataset.den,
           od: +b.dataset.od, do: +b.dataset.do, mistnost: b.dataset.mistnost,
           ucitel: b.dataset.ucitel, paralelky: b.dataset.paralelky, varianty: varianty(b) };
}
// Ktera paralelka je u slotu zvolena. Vic paralelek ve stejny cas a ucebnu je
// typicky sudy vs lichy tyden, a to je rozdil, ktery se ma projevit v rozvrhu.
function zvolena(d) {
  var p = rozvrh[d.slot];
  for (var i = 0; i < d.varianty.length; i++) {
    if (d.varianty[i].p === p) { return d.varianty[i]; }
  }
  return d.varianty[0] || { p: (typeof p === 'string' ? p : ''), pozn: '', u: d.ucitel };
}
// 'S' = jen sude tydny, 'L' = jen liche, '' = kazdy tyden
function tyden(v) {
  var s = (v && v.pozn) || '';
  if (s.indexOf('sud') >= 0) { return 'S'; }
  if (s.indexOf('lich') >= 0) { return 'L'; }
  return '';
}
function popisTydne(v) { var t = tyden(v); return t === 'S' ? 'sudé týdny'
                                                : (t === 'L' ? 'liché týdny' : ''); }
var nabidka = {};                     // kod -> {pr: [sloty], cv: [sloty]}
slotBloky.forEach(function (b) {
  var d = slotData(b);
  var n = nabidka[d.kod] = nabidka[d.kod] || { pr: [], cv: [] };
  n[d.typ].push(d);
});
function cas(m) { return Math.floor(m / 60) + ':' + ('0' + (m % 60)).slice(-2); }
function hodin(m) { return (m / 60).toFixed(1).replace('.', ',').replace(',0', ''); }
function nactiRozvrh() {
  try { rozvrh = JSON.parse(localStorage.getItem(KLIC_ROZVRH)) || {}; } catch (e) { rozvrh = {}; }
  // starsi verze ukladala jen priznak 1; dosad prvni paralelku, at jde variantami cyklovat
  slotBloky.forEach(function (b) {
    var v = rozvrh[b.dataset.slot];
    if (!v) { return; }
    var vs = varianty(b);
    var zna = vs.some(function (x) { return x.p === v; });
    if (!zna && vs.length) { rozvrh[b.dataset.slot] = vs[0].p; }
  });
}
function ulozRozvrh() {
  try { localStorage.setItem(KLIC_ROZVRH, JSON.stringify(rozvrh)); } catch (e) { /* nic */ }
}
function vybraneSloty() {
  return slotBloky.filter(function (b) { return rozvrh[b.dataset.slot]; })
    .map(function (b) { var d = slotData(b); d.varianta = zvolena(d); return d; });
}
function dochChip(kod) {
  var d = DOCHAZKA_DATA[kod];
  if (!d || !d.popis) { return '<span class="tlumene">nezjištěno</span>'; }
  return '<span class="doch ' + (d.trida || '') + '">' + d.popis + '</span>';
}
function vykresliRozvrh() {
  var telo = document.getElementById('rozvrh-telo');
  if (!telo) { return; }
  slotBloky.forEach(function (b) {
    var zap = !!rozvrh[b.dataset.slot];
    b.classList.toggle('vybran-slot', zap);
    var pod = b.querySelector('.blok-pod');
    if (!pod) { return; }
    var vs = varianty(b);
    if (zap && vs.length) {
      var v = zvolena(slotData(b));
      pod.textContent = (v.u || b.dataset.ucitel.split(',')[0]) + ' · ' + b.dataset.mistnost
        + (v.pozn ? ' · ' + v.pozn : (vs.length > 1 ? ' · ' + v.p : ''));
    } else {
      pod.textContent = b.dataset.ucitel.split(',')[0] + ' · ' + b.dataset.mistnost
        + (vs.length > 1 ? ' · ' + vs.length + ' varianty' : '');
    }
    b.classList.toggle('ma-varianty', stavimZapnut && vs.length > 1);
  });
  var sl = vybraneSloty();
  var podle = {};
  sl.forEach(function (x) { (podle[x.kod] = podle[x.kod] || []).push(x); });
  var kody = Object.keys(podle).sort(function (a, b) {
    return zk(a).localeCompare(zk(b), 'cs'); });
  var kredity = kody.reduce(function (a, k) {
    return a + ((kurzPodleKodu[k] && kurzPodleKodu[k].kredity) || 0); }, 0);
  var minut = sl.reduce(function (a, x) { return a + (x.do - x.od); }, 0);
  // hodiny se lisi podle parity tydne, kdyz je mezi vybranym neco sudo/liche
  var minutS = sl.reduce(function (a, x) {
    return a + (tyden(x.varianta) === 'L' ? 0 : x.do - x.od); }, 0);
  var minutL = sl.reduce(function (a, x) {
    return a + (tyden(x.varianta) === 'S' ? 0 : x.do - x.od); }, 0);
  var deliSe = minutS !== minutL || minutS !== minut;
  var dny = {};
  sl.forEach(function (x) { (dny[x.den] = dny[x.den] || []).push(x); });
  var pocetDnu = Object.keys(dny).length;

  document.getElementById('rozvrh-bilance').innerHTML =
      '<div class="bil-polozka celkem"><b>' + kredity + '</b><span>kreditů v ZS</span></div>'
    + '<div class="bil-polozka"><b>' + kody.length + '</b><span>předmětů</span></div>'
    + '<div class="bil-polozka"><b>'
    + (deliSe ? hodin(minutS) + ' / ' + hodin(minutL) : hodin(minut)) + '</b><span>'
    + (deliSe ? 'hodin v sudém / lichém týdnu' : 'hodin výuky týdně') + '</span></div>'
    + '<div class="bil-polozka ' + (pocetDnu && pocetDnu <= 3 ? 'ok' : (pocetDnu >= 5 ? 'chybi' : ''))
    + '"><b>' + pocetDnu + '</b><span>dnů ve škole</span></div>';

  if (!sl.length) {
    telo.innerHTML = '<p class="prazdno">Zatím prázdno — klikni v mřížce nahoře na hodinu, '
                   + 'na kterou chceš chodit. Přednášky i cvičení se klikají zvlášť.</p>';
    return;
  }

  // ---- co mam z ktereho predmetu
  var html = '<div class="tab-obal"><table><thead><tr><th>Předmět</th><th class="c">Kr</th>'
           + '<th>Přednáška</th><th>Cvičení</th><th>Docházka</th></tr></thead><tbody>';
  var bezPr = [], bezCv = [];
  kody.forEach(function (kod) {
    var n = nabidka[kod] || { pr: [], cv: [] };
    var pr = podle[kod].filter(function (x) { return x.typ === 'pr'; });
    var cv = podle[kod].filter(function (x) { return x.typ === 'cv'; });
    if (n.pr.length && !pr.length) { bezPr.push(kod); }
    if (n.cv.length && !cv.length) { bezCv.push(kod); }
    var popis = function (vyb, k, co) {
      if (vyb.length) {
        return vyb.sort(function (a, b) {
            return DNY_POR.indexOf(a.den) - DNY_POR.indexOf(b.den) || a.od - b.od; })
          .map(function (x) { return x.den + ' ' + cas(x.od) + ' <span class="tlumene">'
                                   + x.mistnost + (x.varianta && x.varianta.pozn
                                       ? ', ' + x.varianta.pozn : '')
                                   + '</span>'; }).join('<br>');
      }
      return k.length ? '<span class="chybi-text">chybí ' + co + '</span>'
                      : '<span class="tlumene">nemá</span>';
    };
    html += '<tr><td><a href="#p-' + kod + '"><b>' + zk(kod) + '</b></a>'
          + (plan.hasOwnProperty(kod) ? '' : '<span class="tlumene"> mimo výběr</span>')
          + '</td><td class="c">' + ((kurzPodleKodu[kod] || {}).kredity || 0) + '</td>'
          + '<td>' + popis(pr, n.pr, 'přednáška') + '</td>'
          + '<td>' + popis(cv, n.cv, 'cvičení') + '</td>'
          + '<td>' + dochChip(kod) + '</td></tr>';
  });
  html += '</tbody></table></div>';

  // ---- tyden den po dni
  html += '<div class="sem-souhrn">';
  DNY_POR.forEach(function (den) {
    var d = (dny[den] || []).slice().sort(function (a, b) { return a.od - b.od; });
    if (!d.length) {
      html += '<div class="sem-box volno"><h4>' + den + '</h4>'
            + '<p class="sem-kr">volno</p></div>';
      return;
    }
    var mezery = 0;
    for (var i = 1; i < d.length; i++) { mezery += Math.max(0, d[i].od - d[i - 1].do); }
    // kdyz jsou vsechny hodiny dne ve stejne parite, je to den jen kazdy druhy tyden
    var parity = Array.from(new Set(d.map(function (x) { return tyden(x.varianta); })));
    var celyDen = parity.length === 1 && parity[0] !== ''
      ? (parity[0] === 'S' ? 'jen sudé týdny' : 'jen liché týdny') : '';
    html += '<div class="sem-box"><h4>' + den + '</h4>'
          + '<p class="sem-kr">' + cas(d[0].od) + '–' + cas(d[d.length - 1].do)
          + (celyDen ? ' <span class="tlumene">' + celyDen + '</span>' : '') + '</p>'
          + '<ul>' + d.map(function (x) {
              var t = celyDen ? '' : popisTydne(x.varianta);
              return '<li>' + cas(x.od) + ' ' + zk(x.kod)
                   + (x.typ === 'cv' ? ' <span class="tlumene">cv</span>' : '')
                   + (t ? ' <span class="tlumene">' + t + '</span>' : '') + '</li>';
            }).join('') + '</ul>'
          + (mezery ? '<p class="sem-kolize">okna mezi hodinami: ' + hodin(mezery) + ' h</p>' : '')
          + '</div>';
  });
  html += '</div>';

  // ---- kontroly
  var kontrola = [];
  var kol = [];
  DNY_POR.forEach(function (den) {
    var d = (dny[den] || []).slice().sort(function (a, b) { return a.od - b.od; });
    for (var i = 0; i < d.length; i++) {
      for (var j = i + 1; j < d.length; j++) {
        // sudy a lichy tyden se nemuzou potkat, takze to kolize neni
        var ta = tyden(d[i].varianta), tb = tyden(d[j].varianta);
        if (d[i].do > d[j].od && !(ta && tb && ta !== tb)) {
          kol.push(zk(d[i].kod) + ' × ' + zk(d[j].kod) + ' (' + den + ' ' + cas(d[j].od) + ')');
        }
      }
    }
  });
  kol = Array.from(new Set(kol));
  kontrola.push([kol.length === 0, kol.length
    ? 'Hodiny se překrývají: ' + kol.join('; ')
    : 'Žádné dvě naklikané hodiny se nepřekrývají']);
  // u predmetu, kde se dochazka neresi, je vynechana prednaska zamer, ne chyba
  const bezPrNutne = bezPr.filter(function (k) {
    const d = DOCHAZKA_DATA[k];
    return !d || (d.dochazka !== 'neresi_se' && d.dochazka !== 'nerelevantni');
  });
  const bezPrOk = bezPr.filter(function (k) { return bezPrNutne.indexOf(k) < 0; });
  kontrola.push([bezPrNutne.length === 0, bezPrNutne.length
    ? 'Chybí přednáška: ' + bezPrNutne.map(zk).join(', ')
    : 'U každého předmětu máš přednášku, nebo se u něj docházka neřeší']);
  if (bezPrOk.length) {
    kontrola.push([true, 'Bez přednášky schválně (docházka se neřeší, jede se ze samostudia): '
                       + bezPrOk.map(zk).join(', ')]);
  }
  kontrola.push([bezCv.length === 0, bezCv.length
    ? 'Chybí cvičení (zápočet se obvykle dělá tam): ' + bezCv.map(zk).join(', ')
    : 'U každého předmětu, který cvičení má, ho máš vybrané']);
  const musisFyzicky = sl.filter(function (x) {
    const d = DOCHAZKA_DATA[x.kod];
    return x.typ === 'cv' && d && (d.dochazka === 'povinna' || d.dochazka === 'bodovana');
  });
  const dnyNutne = Array.from(new Set(musisFyzicky.map(function (x) { return x.den; })))
    .sort(function (a, b) { return DNY_POR.indexOf(a) - DNY_POR.indexOf(b); });
  kontrola.push([dnyNutne.length <= 2, dnyNutne.length
    ? 'Fyzicky tam musíš být ' + dnyNutne.length + ' dny v týdnu (' + dnyNutne.join(', ')
      + ') — ' + musisFyzicky.map(function (x) { return zk(x.kod); }).join(', ')
    : 'Žádné vybrané cvičení nemá vynucenou docházku']);

  var musisChodit = kody.filter(function (k) {
    var d = DOCHAZKA_DATA[k];
    return d && (d.dochazka === 'povinna' || d.dochazka === 'bodovana'); });
  if (musisChodit.length) {
    kontrola.push([false, 'Sem se opravdu musí chodit: ' + musisChodit.map(function (k) {
      return zk(k) + ' (' + DOCHAZKA_DATA[k].popis + ')'; }).join(', ')]);
  }
  var neznama = kody.filter(function (k) {
    var d = DOCHAZKA_DATA[k];
    return !d || !d.dochazka || d.dochazka === 'nezjisteno'; });
  if (neznama.length) {
    kontrola.push([true, 'Docházku se nepodařilo dohledat u: ' + neznama.map(zk).join(', ')
                       + ' — ověř před zápisem']);
  }
  var mimoPlan = kody.filter(function (k) { return !plan.hasOwnProperty(k); });
  if (mimoPlan.length) {
    kontrola.push([false, 'V rozvrhu máš předměty, které nejsou v plánovaném výběru: '
                        + mimoPlan.map(zk).join(', ')]);
  }
  var chybiZPlanu = Object.keys(plan).filter(function (k) {
    return plan[k] === 'ZS1' && nabidka[k] && !podle[k]; });
  if (chybiZPlanu.length) {
    kontrola.push([false, 'V plánu na ZS 26/27, ale v rozvrhu nenaklikané: '
                        + chybiZPlanu.map(zk).join(', ')]);
  }
  var planKredity = Object.keys(plan).filter(function (k) { return plan[k] === 'ZS1'; })
    .reduce(function (a, k) { return a + ((kurzPodleKodu[k] || {}).kredity || 0); }, 0);
  if (planKredity) {
    kontrola.push([kredity >= planKredity, 'Rozvrh pokrývá ' + kredity + ' z ' + planKredity
                 + ' kreditů plánovaných na ZS 26/27']);
  }
  html += '<ul class="kontrola">' + kontrola.map(function (c) {
    return '<li class="' + (c[0] ? 'ok' : 'chybi') + '">' + (c[0] ? '✓ ' : '✗ ') + c[1] + '</li>';
  }).join('') + '</ul>';
  html += '<p class="vysvetlivka">Kolize se počítají mezi konkrétními naklikanými hodinami, '
        + 'ne mezi předměty — u cvičení si vybíráš jednu paralelku z několika, takže dvě '
        + 'cvičení ve stejný čas jsou kolize jen tehdy, když si obě opravdu zapíšeš. '
        + 'Rozvrh je předběžný („v působnosti rozvrhové komise"), před zápisem ho přetáhni '
        + 'ze SIS znovu.</p>';

  html += '<details><summary>Vypsat rozvrh jako text</summary><textarea id="export-rozvrh" '
        + 'rows="8" spellcheck="false" readonly>' + sl.slice()
      .sort(function (a, b) {
        return DNY_POR.indexOf(a.den) - DNY_POR.indexOf(b.den) || a.od - b.od; })
      .map(function (x) {
        return x.den + ' ' + cas(x.od) + '–' + cas(x.do) + '  ' + zk(x.kod)
             + ' (' + (x.typ === 'pr' ? 'přednáška' : 'cvičení') + ', ' + x.mistnost
             + ', ' + ((x.varianta && x.varianta.p) || x.paralelky)
             + (x.varianta && x.varianta.pozn ? ', ' + x.varianta.pozn : '')
             + ')'; }).join('\n')
      + '</textarea></details>';
  telo.innerHTML = html;
}
// Klik cykluje: nevybráno -> 1. paralelka -> 2. paralelka -> ... -> nevybráno.
// U slotu s jedinou paralelkou je to prosty prepinac jako drive.
function prepniSlot(b) {
  var vs = varianty(b);
  var ted = rozvrh[b.dataset.slot];
  var i = -1;
  for (var j = 0; j < vs.length; j++) { if (vs[j].p === ted) { i = j; } }
  if (!ted) { rozvrh[b.dataset.slot] = vs.length ? vs[0].p : '1'; }
  else if (i >= 0 && i + 1 < vs.length) { rozvrh[b.dataset.slot] = vs[i + 1].p; }
  else { delete rozvrh[b.dataset.slot]; }
  ulozRozvrh(); vykresliRozvrh(); rozloz();
  if (vs.length > 1) {
    var v = rozvrh[b.dataset.slot];
    var vyb = vs.filter(function (x) { return x.p === v; })[0];
    hlaska('hlaska-rozvrh', vyb
      ? zk(b.dataset.kod) + ': ' + vyb.p + (vyb.pozn ? ' (' + vyb.pozn + ')' : '')
        + ' — dalším klikem přepneš na další z ' + vs.length + ' paralelek'
      : zk(b.dataset.kod) + ': paralelka odebrána z rozvrhu');
  }
}
slotBloky.forEach(function (b) {
  b.addEventListener('click', function (e) {
    if (!stavimZapnut) { return; }
    e.preventDefault();
    prepniSlot(b);
  });
});
filtrDoplnek = function (b) {
  return jenMoje && stavimZapnut && !rozvrh[b.dataset.slot];
};
var jenMojeBox = document.getElementById('f-jen-moje');
if (jenMojeBox) {
  jenMojeBox.addEventListener('change', function () { jenMoje = this.checked; rozloz(); });
}
document.getElementById('rezim-rozvrh').addEventListener('click', function () {
  stavimZapnut = !stavimZapnut;
  document.body.classList.toggle('stavim', stavimZapnut);
  document.getElementById('builder-telo').hidden = !stavimZapnut;
  this.textContent = stavimZapnut ? 'Vypnout stavbu rozvrhu' : 'Zapnout stavbu rozvrhu';
  if (stavimZapnut) {
    var cv = document.getElementById('f-cv');
    if (cv && !cv.checked) { cv.checked = true; }
    vykresliRozvrh();
  }
  rozloz();
});
document.getElementById('z-repa-rozvrh').addEventListener('click', function () {
  const znam = {};
  slotBloky.forEach(function (b) { znam[b.dataset.slot] = 1; });
  const novy = {};
  DOPORUCENY_ROZVRH.forEach(function (s) { if (znam[s[0]]) { novy[s[0]] = s[1]; } });
  if (!Object.keys(novy).length) {
    hlaska('hlaska-rozvrh', 'Doporučený rozvrh v repozitáři zatím není.'); return;
  }
  rozvrh = novy;
  ulozRozvrh(); vykresliRozvrh(); rozloz();
  hlaska('hlaska-rozvrh', 'Načten doporučený rozvrh z repozitáře — '
       + Object.keys(novy).length + ' hodin. Přednášky v něm schválně nejsou.');
});
document.getElementById('z-planu').addEventListener('click', function () {
  var kolik = 0;
  Object.keys(plan).forEach(function (kod) {
    if (plan[kod] !== 'ZS1' || !nabidka[kod]) { return; }
    var prvni = function (x) { return x.varianty.length ? x.varianty[0].p : '1'; };
    nabidka[kod].pr.forEach(function (x) {
      if (!rozvrh[x.slot]) { kolik++; }
      rozvrh[x.slot] = rozvrh[x.slot] || prvni(x);
    });
    if (nabidka[kod].cv.length === 1) {
      var x = nabidka[kod].cv[0];
      if (!rozvrh[x.slot]) { kolik++; }
      rozvrh[x.slot] = rozvrh[x.slot] || prvni(x);
    }
  });
  ulozRozvrh(); vykresliRozvrh(); rozloz();
  hlaska('hlaska-rozvrh', kolik
    ? 'Přidáno ' + kolik + ' hodin z předmětů plánovaných na ZS 26/27. Cvičení jen tam, kde je jediná paralelka.'
    : 'Nic k přidání — buď plán na ZS 26/27 nic nemá, nebo už je všechno naklikané.');
});
document.getElementById('vsechny-prednasky').addEventListener('click', function () {
  slotBloky.forEach(function (b) {
    if (b.dataset.typ !== 'pr' || rozvrh[b.dataset.slot]) { return; }
    var vs = varianty(b);
    rozvrh[b.dataset.slot] = vs.length ? vs[0].p : '1';
  });
  ulozRozvrh(); vykresliRozvrh(); rozloz();
  hlaska('hlaska-rozvrh', 'Přidány všechny přednášky z mřížky — teď z nich ubírej.');
});
document.getElementById('vycisti-rozvrh').addEventListener('click', function () {
  if (!Object.keys(rozvrh).length) {
    hlaska('hlaska-rozvrh', 'Rozvrh je už prázdný.'); return;
  }
  potvrd(this, 'Opravdu vyprázdnit?', function () {
    rozvrh = {}; ulozRozvrh(); vykresliRozvrh(); rozloz();
    hlaska('hlaska-rozvrh', 'Rozvrh vyprázdněn.');
  });
});
nactiRozvrh();
if (Object.keys(rozvrh).length) { document.getElementById('rezim-rozvrh').click(); }
else { vykresliRozvrh(); }
"""


CSS = r"""
:root {
  --bg:#eceff4; --papir:#fbfcfd; --ink:#141a21; --tlum:#5d6875; --linka:#d3dae3;
  --akcent:#9c2230; --akcent-tlum:#f2dfe1;
  --povinny:#3f4a58; --profilujici:#9c2230; --rozsirujici:#1c6b66; --volitelny:#8a6212;
  --dobra:#1c6b66; --stredni:#8a6212; --slaba:#9c2230;
  --zima:#1f5fa8; --leto:#2e7d1e;
  --stin:0 1px 2px rgba(20,26,33,.06), 0 8px 24px -16px rgba(20,26,33,.28);
  --ctvrt:13px;
  --serif:"Newsreader",Georgia,"Times New Roman",serif;
  --sans:"IBM Plex Sans",-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Menlo,monospace;
}
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
  --bg:#11161c; --papir:#181f27; --ink:#e6ecf3; --tlum:#9aa7b6; --linka:#2a333e;
  --akcent:#e2707c; --akcent-tlum:#3a222a;
  --povinny:#8c9aab; --profilujici:#e2707c; --rozsirujici:#54b3ab; --volitelny:#d2a44f;
  --dobra:#54b3ab; --stredni:#d2a44f; --slaba:#e2707c;
  --zima:#79b0e6; --leto:#78c94e;
  --stin:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
}}
:root[data-theme="dark"]{
  --bg:#11161c; --papir:#181f27; --ink:#e6ecf3; --tlum:#9aa7b6; --linka:#2a333e;
  --akcent:#e2707c; --akcent-tlum:#3a222a;
  --povinny:#8c9aab; --profilujici:#e2707c; --rozsirujici:#54b3ab; --volitelny:#d2a44f;
  --dobra:#54b3ab; --stredni:#d2a44f; --slaba:#e2707c;
  --zima:#79b0e6; --leto:#78c94e;
  --stin:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}
main{max-width:1120px;margin:0 auto;padding:clamp(28px,5vw,60px) clamp(16px,4vw,40px) 72px}
#prehled{display:flex;flex-direction:column;gap:clamp(30px,4.5vw,52px)}
.detail{display:flex;flex-direction:column;gap:clamp(20px,2.6vw,30px)}
/* uvnitr bloku uz zadne velke mezery — nadpis, vysvetlivka a obsah drzi u sebe */
.detail-blok{display:block}
.detail-blok+.detail-blok{border-top:1px solid var(--linka);padding-top:clamp(18px,2.4vw,26px)}
.detail-blok.pruhy{border-top:0;padding-top:0;display:flex;flex-direction:column;gap:10px}
.detail-blok>.podnadpis{margin:0 0 8px}
.detail-blok>.vysvetlivka{margin:0 0 14px}
.detail-blok>.podnadpis+.vysvetlivka{margin-top:-2px}
.detail-blok>.tab-obal{margin-top:14px}
.detail-blok>.ucitel{margin-top:14px}
.detail-blok>.prakticky{margin-top:12px}
.detail-blok>.mini{margin-top:16px}
.detail-blok>details{margin-top:12px}
[hidden]{display:none !important}   /* jinak by tridni pravidlo prebilo UA styl */
h1,h2,h3,h4{text-wrap:balance;margin:0}
code{font-family:var(--mono);font-size:.92em}
a{color:var(--akcent)}
a:focus-visible,summary:focus-visible{outline:2px solid var(--akcent);outline-offset:3px}

.uvod{display:flex;flex-direction:column;gap:14px;border-bottom:1px solid var(--linka);
  padding-bottom:clamp(22px,4vw,32px)}
.eyebrow{margin:0;font-size:12px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--tlum);font-weight:500}
h1{font-family:var(--serif);font-size:clamp(38px,7vw,60px);font-weight:600;line-height:1.02;
  letter-spacing:-.02em}
.perex{margin:0;max-width:64ch;color:var(--tlum);font-size:17px}
.souhrn{margin:4px 0 0;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;
  font-family:var(--mono);font-size:13px;color:var(--tlum);font-variant-numeric:tabular-nums}
.souhrn b{font-family:var(--serif);font-size:32px;color:var(--akcent);line-height:1}
.souhrn span:not(:last-child)::after{content:" ·";color:var(--linka)}
.nadpis{font-family:var(--serif);font-size:23px;font-weight:600;margin-bottom:10px}
.vysvetlivka{margin:0 0 14px;max-width:70ch;font-size:14px;color:var(--tlum)}

.mrizka{display:grid;grid-template-columns:52px repeat(5,1fr);gap:0 6px;
  background:var(--papir);border:1px solid var(--linka);border-radius:3px;
  padding:10px 12px 16px;overflow-x:auto;box-shadow:var(--stin)}
.hlavicka{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--tlum);
  padding-bottom:6px;text-align:center}
.cas{font-family:var(--mono);font-size:11px;color:var(--tlum);text-align:right;
  padding-right:8px;transform:translateY(-.5em)}
.pruh{border-top:1px solid var(--linka)}
.blok{--i:0;--n:1;width:calc((100% - (var(--n) - 1)*2px)/var(--n));
  margin-left:calc(var(--i)*100%/var(--n));border-radius:2px;padding:4px 6px;
  font-size:11.5px;line-height:1.2;overflow:hidden;color:#fff;background:var(--barva);
  text-decoration:none;display:flex;flex-direction:column;gap:1px}
.blok b{font-weight:500;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;line-clamp:2}
.blok span{opacity:.85;font-size:10.5px}
.blok.cviceni{opacity:.72}
.blok:hover{outline:2px solid var(--ink);outline-offset:-2px;opacity:1}
body.stavim .blok:not(.vybran-slot):hover{opacity:.7;filter:none}
.filtr{display:flex;flex-direction:column;gap:10px;margin-bottom:14px}
.filtr-radek{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.filtr-radek.chipy{gap:7px}
.filtr-prepinac{font-size:13.5px;display:flex;align-items:center;gap:6px;cursor:pointer}
.filtr-oddel{width:1px;height:18px;background:var(--linka)}
.filtr-tlac{font:inherit;font-size:12.5px;padding:3px 10px;border:1px solid var(--linka);
  border-radius:2px;background:var(--papir);color:var(--ink);cursor:pointer}
.filtr-tlac:hover{border-color:var(--akcent);color:var(--akcent)}
.filtr-stav{font-family:var(--mono);font-size:12px;color:var(--tlum);margin-left:auto;
  font-variant-numeric:tabular-nums}
.filtr-chip{font-size:12.5px;display:flex;align-items:center;gap:6px;cursor:pointer;
  padding:3px 9px 3px 7px;border:1px solid var(--linka);border-radius:2px;
  background:var(--papir);border-left:3px solid var(--barva)}
.filtr-chip:has(input:not(:checked)){opacity:.45}
.filtr-chip input,.filtr-prepinac input{accent-color:var(--akcent);margin:0}
.legenda{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin:12px 0 0;
  font-size:13px;color:var(--tlum)}
.vzorek{width:14px;height:14px;border-radius:2px;background:var(--barva);
  display:inline-block;margin-right:6px;vertical-align:-2px}
.cviceni-vzorek{background:var(--povinny);opacity:.55}
.sk-povinny{--barva:var(--povinny)} .sk-profilujici{--barva:var(--profilujici)}
.sk-rozsirujici{--barva:var(--rozsirujici)} .sk-volitelny{--barva:var(--volitelny)}

.dlazdice-mriz{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(276px,1fr))}
.dlazdice{background:var(--papir);border:1px solid var(--linka);
  border-left:3px solid var(--barva);border-radius:3px;padding:15px 17px;
  display:flex;flex-direction:column;gap:8px;box-shadow:var(--stin);
  text-decoration:none;color:inherit;transition:transform .12s ease,box-shadow .12s ease}
.dlazdice:hover{transform:translateY(-2px);
  box-shadow:0 2px 4px rgba(20,26,33,.08),0 14px 30px -18px rgba(20,26,33,.5)}
.dlazdice header{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.dlazdice h3{font-family:var(--serif);font-size:19px;font-weight:600;line-height:1.2}
.kr{font-family:var(--mono);font-size:19px;font-variant-numeric:tabular-nums;line-height:1}
.kr small{font-size:11px;color:var(--tlum);margin-left:2px}
.dlazdice .kod{margin:0;font-family:var(--mono);font-size:12px;color:var(--tlum)}
.dlazdice-rozvrh,.dlazdice-anketa{margin:0;font-size:13px;color:var(--tlum)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-size:11px;letter-spacing:.03em;padding:2px 8px;border-radius:2px;
  border:1px solid var(--linka);color:var(--tlum);white-space:nowrap}
.chip.sk-povinny,.chip.sk-profilujici,.chip.sk-rozsirujici,.chip.sk-volitelny{
  color:var(--barva);border-color:color-mix(in srgb,var(--barva) 45%,transparent)}
.chip.szz{background:var(--akcent-tlum);border-color:transparent;color:var(--akcent)}
.chip.varovani{border-style:dashed;color:var(--slaba);border-color:var(--slaba)}
.znamka{font-family:var(--mono);font-variant-numeric:tabular-nums;font-weight:500;
  color:var(--dobra)}
.znamka.stredni{color:var(--stredni)} .znamka.slaba{color:var(--slaba)}
.znamka.bez{color:var(--tlum);font-weight:400}
.znamka.velka{font-size:24px;margin-left:auto}

.detail{scroll-margin-top:20px}
.zpet{font-size:14px;text-decoration:none;align-self:flex-start}
.zpet:hover{text-decoration:underline}
.detail-hlava{display:flex;flex-direction:column;gap:10px;
  border-bottom:1px solid var(--linka);padding-bottom:20px}
.detail-hlava h2{font-family:var(--serif);font-size:clamp(30px,5vw,44px);font-weight:600;
  line-height:1.05;letter-spacing:-.015em}
.detail-meta{margin:0;font-family:var(--mono);font-size:13px;color:var(--tlum);
  font-variant-numeric:tabular-nums}
.odkazy{margin:6px 0 0;display:flex;flex-wrap:wrap;gap:8px}
.odkazy a{font-size:12.5px;padding:4px 10px;border:1px solid var(--linka);border-radius:2px;
  text-decoration:none;background:var(--papir)}
.odkazy a:hover{border-color:var(--akcent)}
.podnadpis{font-family:var(--serif);font-size:22px;font-weight:600}
.mini{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--tlum);
  font-weight:500;margin-top:14px}
.relevance{margin:0;max-width:68ch;font-size:17px}
.detail p{margin:8px 0 0;max-width:74ch}
.sylabus{color:var(--tlum);font-size:15px}
.meta-jazyk{margin-left:10px;padding:1px 7px;border:1px solid var(--linka);border-radius:2px}
td.tlumene{color:var(--tlum)}
.varovani-pruh{margin:0;padding:12px 16px;border-left:3px solid var(--slaba);
  background:var(--akcent-tlum);color:var(--ink);border-radius:2px;font-size:14.5px}
.prazdno{color:var(--tlum);font-size:14px;font-style:italic}
.body{margin:8px 0 0;padding-left:0;list-style:none;display:flex;flex-direction:column;gap:6px;
  max-width:74ch}
.body li{padding-left:18px;position:relative;font-size:15px}
.body li::before{content:"";position:absolute;left:2px;top:.62em;width:6px;height:6px;
  border-radius:50%;background:var(--barva-odrazky,var(--linka))}
.dvojice{display:grid;gap:10px 32px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
  align-items:start}
.pozor{margin-top:16px;padding:12px 16px 14px;border-left:3px solid var(--stredni);
  background:var(--papir);border-radius:2px}
.pozor .mini{margin-top:0;color:var(--stredni)}
.pozor .body li::before{background:var(--stredni)}
.detail-mrizka{margin-top:12px;margin-bottom:16px}

/* --- planovaci rezim --- */
.planovac{background:var(--papir);border:1px solid var(--linka);border-radius:3px;
  padding:20px 22px;box-shadow:var(--stin)}
.planovac-hlava{display:flex;gap:20px;align-items:flex-start;justify-content:space-between;
  flex-wrap:wrap}
.planovac-hlava .nadpis{margin-bottom:6px}
.planovac-hlava .vysvetlivka{margin:0;max-width:62ch}
.rezim-tlac{font:inherit;font-size:14px;padding:9px 16px;border:1px solid var(--akcent);
  background:var(--akcent);color:#fff;border-radius:2px;cursor:pointer;white-space:nowrap}
.rezim-tlac:hover{filter:brightness(1.08)}
body.planuji .rezim-tlac{background:transparent;color:var(--akcent)}
#planovac-telo{display:flex;flex-direction:column;gap:22px;margin-top:20px;
  border-top:1px solid var(--linka);padding-top:20px}
.souhrn-pruh{display:flex;flex-wrap:wrap;gap:10px}
.bil-polozka{border:1px solid var(--linka);border-radius:2px;padding:8px 14px;min-width:104px;
  display:flex;flex-direction:column;gap:2px;border-left:3px solid var(--barva,var(--linka))}
.bil-polozka b{font-family:var(--mono);font-size:21px;line-height:1;
  font-variant-numeric:tabular-nums}
.bil-polozka span{font-size:11.5px;color:var(--tlum)}
.bil-polozka.celkem{--barva:var(--akcent)} .bil-polozka.celkem b{color:var(--akcent)}
.bil-polozka.ok b{color:var(--dobra)} .bil-polozka.chybi b{color:var(--slaba)}
.planovac-mriz{display:grid;gap:26px 32px;grid-template-columns:minmax(260px,1fr) minmax(320px,1.6fr)}
.szz-radek{display:block;padding:10px 0 10px 12px;
  border-left:3px solid var(--linka);margin-bottom:8px}
.szz-radek>summary{cursor:pointer;display:flex;flex-direction:column;gap:2px;
  list-style:none}
.szz-radek>summary::-webkit-details-marker{display:none}
.szz-radek>summary b::before{content:'▸ ';color:var(--tlum);font-weight:400}
.szz-radek[open]>summary b::before{content:'▾ '}
.szz-radek>summary:hover b{color:var(--akcent)}
.szz-radek.ok{border-color:var(--dobra)} .szz-radek.castecne{border-color:var(--stredni)}
.szz-radek.chybi{border-color:var(--slaba)}
.szz-radek span{font-size:13px;color:var(--tlum)}
.tab-semestry tbody.sem-skupina + tbody.sem-skupina .sem-hlava th{padding-top:16px}
.sem-hlava th{text-align:left;padding:8px 0 6px;border-bottom:1px solid var(--linka);
  font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink)}
.sem-hlava-obal{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 10px}
.sem-hlava-obal>span:first-child{font-weight:700}
.sem-hlava-kr{font-family:var(--mono);font-size:12px;letter-spacing:0;
  text-transform:none;color:var(--tlum);font-weight:400}
.sem-skupina.hodne .sem-hlava-kr{color:var(--stredni)}
.sem-skupina.nezarazene .sem-hlava th{color:var(--slaba);border-bottom-color:var(--slaba)}
.sem-skupina.nezarazene .sem-hlava-kr{color:var(--slaba)}
.sem-volna td{color:var(--tlum);font-style:italic;font-size:13px}
/* --- skupiny dlazdic, tagy a filtr predmetu --- */
.skupina-sekce{margin-top:26px}
.skupina-nadpis{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;
  font-family:var(--serif);font-size:21px;font-weight:600;margin:0 0 12px;
  padding-bottom:6px;border-bottom:2px solid var(--barva)}
.skupina-nadpis span{font-family:var(--sans);font-size:12.5px;font-weight:400;color:var(--tlum)}
.skupina-vybrano:empty{display:none}
.skupina-vybrano{font-family:var(--mono)!important;font-size:12px!important;
  padding:2px 8px;border-radius:2px;border:1px solid var(--linka);white-space:nowrap}
.skupina-vybrano.ok{color:var(--dobra)!important;border-color:var(--dobra)}
.skupina-vybrano.chybi{color:var(--slaba)!important;border-color:var(--slaba)}
.skupina-vybrano.neutral{color:var(--akcent)!important;border-color:var(--akcent)}
.chip.tag-chip{border-style:dashed}
.sem-znak{font-family:var(--mono);font-weight:500;letter-spacing:.04em;
  padding:0 5px;border-radius:2px;border:1px solid currentColor}
.sem-znak.zima{color:var(--zima)}
.sem-znak.leto{color:var(--leto)}
.chips.tagy{margin-top:-2px}
.filtr-dlazdic{margin-bottom:6px}
#hledani{font:inherit;font-size:14px;padding:6px 10px;min-width:230px;
  border:1px solid var(--linka);border-radius:2px;background:var(--papir);color:var(--ink)}
.tagy-radek{gap:6px}
.tag-tlac{font:inherit;font-size:12px;padding:4px 10px;border:1px dashed var(--linka);
  background:transparent;color:var(--tlum);border-radius:2px;cursor:pointer;
  display:inline-flex;align-items:center;gap:6px}
.tag-tlac:hover{border-color:var(--akcent);color:var(--akcent)}
.tag-tlac.aktivni{background:var(--akcent);border-color:var(--akcent);border-style:solid;color:#fff}
.tag-pocet{font-family:var(--mono);font-size:10.5px;opacity:.75}
.zam-tlac{font:inherit;font-size:12px;padding:4px 10px;border:1px dashed var(--profilujici);
  border-radius:999px;background:none;color:var(--text);cursor:pointer;
  display:inline-flex;gap:6px;align-items:center}
.zam-tlac:hover{border-color:var(--profilujici);color:var(--profilujici)}
.zam-tlac.aktivni{background:var(--profilujici);border-color:var(--profilujici);
  border-style:solid;color:#fff}
.filtr-popisek{font-size:12px;opacity:.7;align-self:center}
.zamereni-radek{align-items:center}
/* --- anketa k predmetu jako celku --- */
.predmet-anketa{display:flex;flex-wrap:wrap;gap:16px 22px;align-items:flex-start;
  margin-top:14px;background:var(--papir);border:1px solid var(--linka);border-radius:3px;
  padding:16px 18px}
.predmet-anketa .shrnuti{margin-top:0;padding-top:0;border-top:0}
.predmet-znamka{display:flex;align-items:center;gap:10px;min-width:190px}
.predmet-znamka p{margin:0;font-size:12.5px;color:var(--tlum);line-height:1.35}
.predmet-anketa .shrnuti{flex:1;min-width:280px}
.kod-odkaz{font-family:var(--mono);font-size:12.5px;color:var(--tlum);text-decoration:none;
  border-bottom:1px dotted var(--linka)}
.kod-odkaz:hover{color:var(--akcent);border-bottom-color:var(--akcent)}
.sem-volba{display:flex;flex-wrap:wrap;gap:4px}
.sem-tlac{font:inherit;font-size:11.5px;padding:3px 8px;border:1px solid var(--linka);
  background:transparent;color:var(--tlum);border-radius:2px;cursor:pointer}
.sem-tlac:hover{border-color:var(--akcent);color:var(--akcent)}
.sem-tlac.aktivni{background:var(--akcent);border-color:var(--akcent);color:#fff}
.sem-tlac.zrus{color:var(--slaba)}
.sem-souhrn{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
  margin-top:16px}
.sem-box{border:1px solid var(--linka);border-radius:2px;padding:10px 12px}
.sem-box.hodne{border-color:var(--stredni)}
.sem-box h4{font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--tlum);
  font-weight:500}
.sem-kr{margin:2px 0 6px;font-family:var(--mono);font-size:19px;
  font-variant-numeric:tabular-nums}
.sem-box.hodne .sem-kr{color:var(--stredni)}
.sem-box ul{margin:0;padding-left:16px;font-size:12.5px;color:var(--tlum)}
.sem-kolize{margin:6px 0 0;font-size:11.5px;color:var(--slaba)}
.kontrola{margin:16px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:5px;
  font-size:14px}
.kontrola .ok{color:var(--dobra)} .kontrola .chybi{color:var(--slaba)}
#export{width:100%;margin-top:10px;font-family:var(--mono);font-size:12px;padding:10px;
  border:1px solid var(--linka);border-radius:2px;background:var(--bg);color:var(--ink)}
.lista-hlaska{margin:0;min-height:1.2em;font-size:13px;color:var(--akcent)}
.lista-tlac.ceka{border-color:var(--slaba);color:var(--slaba);font-weight:500}
.lista-tlac.hlavni{border-color:var(--akcent);color:var(--akcent);font-weight:500}
#nazev-verze{font:inherit;font-size:12.5px;padding:3px 8px;border:1px solid var(--linka);
  border-radius:2px;background:var(--papir);color:var(--ink);width:150px}
.szz-temata{margin:8px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:5px}
.szz-temata li{font-size:13px;padding-left:16px;position:relative;line-height:1.4}
.szz-temata li::before{content:"";position:absolute;left:0;top:.5em;width:7px;height:7px;
  border-radius:50%;background:var(--tlum)}
.szz-temata li.ok::before{background:var(--dobra)}
.szz-temata li.castecne::before{background:var(--stredni)}
.szz-temata li.chybi::before{background:var(--slaba)}
.szz-temata li b{font-weight:500}
.szz-temata li span{display:block;font-size:12px;color:var(--tlum)}

/* rezim stavby rozvrhu */
body.stavim .blok{cursor:pointer}
body.stavim .blok:not(.vybran-slot){opacity:.24;filter:grayscale(.55)}
body.stavim .blok.vybran-slot{opacity:1;outline:2px solid var(--ink);outline-offset:-2px;
  box-shadow:0 0 0 2px var(--papir)}
/* blok, kde je ve stejny cas a ucebne vic paralelek — klik mezi nimi cykluje */
body.stavim .blok.ma-varianty{position:relative}
body.stavim .blok.ma-varianty::after{content:"⇄";position:absolute;top:1px;right:3px;
  font-size:10px;line-height:1;opacity:.75}
.sem-box.volno{opacity:.5}
.sem-box.volno .sem-kr{font-size:14px;color:var(--tlum)}
.chybi-text{color:var(--slaba)}
.doch{font-size:11.5px;padding:1px 7px;border:1px solid var(--linka);border-radius:2px;
  white-space:nowrap}
.doch.slaba{color:var(--slaba);border-color:var(--slaba)}
.doch.stredni{color:var(--stredni);border-color:var(--stredni)}
.doch.dobra{color:var(--dobra);border-color:var(--dobra)}
.chip.dochazka-chip.slaba{color:var(--slaba);border-color:var(--slaba)}
.chip.dochazka-chip.stredni{color:var(--stredni);border-color:var(--stredni)}
.chip.nahravky-chip{color:var(--dobra);border-color:var(--dobra)}
#export-rozvrh{width:100%;margin-top:10px;font-family:var(--mono);font-size:12px;padding:10px;
  border:1px solid var(--linka);border-radius:2px;background:var(--bg);color:var(--ink)}

/* prakticke info ze stranek kurzu */
.prakticky{display:grid;gap:12px 28px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
  margin-top:10px}
.prakt-polozka{border-left:3px solid var(--linka);padding:2px 0 2px 12px}
.prakt-polozka.dobra{border-color:var(--dobra)}
.prakt-polozka.stredni{border-color:var(--stredni)}
.prakt-polozka.slaba{border-color:var(--slaba)}
.prakt-polozka .mini{margin-top:0}
.prakt-polozka p{margin:2px 0 0;font-size:14px}
.doklad{color:var(--tlum);font-size:13px;font-style:italic}

.vybrano-znacka{display:none;font-size:10px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--akcent);border:1px solid var(--akcent);border-radius:2px;padding:2px 6px;
  white-space:nowrap;align-self:center}
.dlazdice header{gap:8px}
.dlazdice h3{flex:1;min-width:0}
body.planuji .dlazdice{cursor:pointer}
body.planuji .dlazdice.vybrana{border-color:var(--akcent);
  box-shadow:0 0 0 1px var(--akcent),var(--stin)}
body.planuji .dlazdice.vybrana .vybrano-znacka{display:inline-block}
body.planuji .na-detail{display:inline-block}
.dlazdice h3 a{color:inherit;text-decoration:none}
.na-detail{display:none;font-size:12px;margin-top:2px;text-decoration:none}
.na-detail:hover{text-decoration:underline}
.planovac-lista{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;
  justify-content:space-between;padding-bottom:16px;border-bottom:1px solid var(--linka)}
.usek-volba{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;font-size:13.5px}
.usek-volba label{display:flex;align-items:center;gap:5px;cursor:pointer}
.usek-volba input{accent-color:var(--akcent);margin:0}
.lista-popis{color:var(--tlum);font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.ulozene{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.lista-tlac{font:inherit;font-size:12.5px;padding:4px 10px;border:1px solid var(--linka);
  border-radius:2px;background:var(--papir);color:var(--ink);cursor:pointer}
.lista-tlac:hover{border-color:var(--akcent);color:var(--akcent)}
.lista-tlac.zrus{color:var(--slaba);border-color:color-mix(in srgb,var(--slaba) 40%,transparent)}
#verze{font:inherit;font-size:12.5px;padding:4px 8px;border:1px solid var(--linka);
  border-radius:2px;background:var(--papir);color:var(--ink);max-width:190px}
.dlazdice h3 a:hover{text-decoration:underline}
@media (max-width:780px){ .planovac-mriz{grid-template-columns:1fr} }
.budova{margin-left:6px;font-size:11px;color:var(--stredni);
  border:1px solid var(--stredni);border-radius:2px;padding:0 5px}
.chip.budova-chip{color:var(--stredni);border-color:var(--stredni)}
.jinde-pruh{margin:0;padding:12px 16px;border-left:3px solid var(--stredni);
  background:var(--papir);border-radius:2px;font-size:14.5px}
.shrnuti{margin-top:12px;padding-top:12px;border-top:1px dashed var(--linka)}
.shrnuti-veta{margin:0 0 10px;font-size:15.5px}
.shrnuti-zdroj{margin:10px 0 0;font-size:12px;color:var(--tlum);font-family:var(--mono)}
.rozpor{margin:10px 0 0;font-size:14px;color:var(--ink);padding:8px 12px;
  border-left:3px solid var(--stredni);background:var(--bg);border-radius:2px}
h5.mini{margin:0 0 2px}
.zeleny{color:var(--dobra)} .cerveny{color:var(--slaba)}
.plusy{--barva-odrazky:var(--dobra)} .minusy{--barva-odrazky:var(--slaba)}
.plusy li,.minusy li{font-size:14.5px}
.mrizka.maly{padding:8px 10px 12px;max-width:640px}
.mrizka.maly .blok{font-size:11px}
.pata-detailu{color:var(--tlum);font-size:13px;border-top:1px solid var(--linka);
  padding-top:16px}

.tab-obal{overflow-x:auto;background:var(--papir);border:1px solid var(--linka);
  border-radius:3px;box-shadow:var(--stin)}
.tab-obal.uzka{box-shadow:none;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:560px}
th,td{text-align:left;padding:8px 13px;border-bottom:1px solid var(--linka);vertical-align:top}
thead th{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--tlum);
  font-weight:500;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
td.c,th.c{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}

.ucitel+.ucitel{margin-top:14px}
.ucitel{background:var(--papir);border:1px solid var(--linka);border-radius:3px;
  padding:16px 18px;margin-top:12px;box-shadow:var(--stin)}
.ucitel header{display:flex;align-items:center;gap:12px}
.ucitel h4{font-family:var(--serif);font-size:20px;font-weight:600}
.poradi{font-family:var(--mono);font-size:12px;color:var(--tlum);border:1px solid var(--linka);
  border-radius:50%;width:24px;height:24px;display:grid;place-items:center;flex:none}
.role{margin:0;font-size:13px;color:var(--tlum)}
.roky{margin:2px 0 0;font-size:12.5px;color:var(--tlum);font-family:var(--mono)}
.roky .tlumene{opacity:.75}
.ucitel h4 .odznak-zs,.ucitel h4 .odznak-drive{font-family:var(--sans);font-size:11px;
  font-weight:600;letter-spacing:.02em;text-transform:lowercase;vertical-align:middle;
  padding:2px 7px;border-radius:999px;border:1px solid var(--linka);white-space:nowrap}
.ucitel h4 .odznak-zs{background:var(--akcent);color:#fff;border-color:transparent}
.ucitel h4 .odznak-drive{color:var(--tlum)}
.ucitel.drive{background:transparent;box-shadow:none;border-style:dashed}
.drivejsi{margin-top:14px;border-top:1px dashed var(--linka);padding-top:10px}
.drivejsi>summary{font-size:14px;color:var(--tlum);cursor:pointer}
.kom-predmet{margin-top:12px}
.kom-predmet>summary{font-size:14px;color:var(--tlum);cursor:pointer}
details{margin-top:10px}
summary{cursor:pointer;font-size:13.5px;color:var(--akcent)}
.komentare{margin:10px 0 0;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px}
.komentare li{font-size:14.5px;border-left:2px solid var(--linka);padding-left:12px}
.kdy{display:block;font-family:var(--mono);font-size:11.5px;color:var(--tlum);margin-bottom:2px}

footer{border-top:1px solid var(--linka);padding-top:20px;color:var(--tlum);font-size:13px;
  display:flex;flex-direction:column;gap:6px}
footer p{margin:0;max-width:78ch}
@media (max-width:620px){
  .dlazdice-mriz{grid-template-columns:1fr}
  .mrizka{font-size:10px}
}
"""

if __name__ == "__main__":
    main()
