# Datová vrstva: co odkud je a jak se obnovuje

SIS má veřejně, bez přihlášení, jak detail předmětu, tak CSV export rozvrhu
i výsledky studentských anket. Všechno se tahá skriptem.

## Přehled

| Soubor | Kdo ho píše | Co v něm je |
|---|---|---|
| `data/program.json` | **ručně / skill** | Program, zaměření, kreditová minima, SZZ okruhy, semestr. Jediné místo, kde se tohle mění. |
| `data/predmety.csv` | **ručně** | Které předměty se sledují: `kod, vrstva, zamereni, skupina, szz, plan_semestr, stav, poznamka` |
| `data/relevance.csv` | **ručně** | `kod, zkratka, relevance` — lidský název předmětu a volitelně odstavec „proč to chci" |
| `data/rozvrh_vyber.csv` | **ručně** | `kod, paralelka, poznamka` — konkrétní vybrané paralelky |
| `data/ankety.csv` | **ručně** | Ověřený závěr uživatele o anketě (`kod, znamka, respondentu, shrnuti`) |
| `data/sis.csv` | `tools/sis.py` | Název, kredity, rozsah, examinace, **stav předmětu**, garant, vyučující, neslučitelnost |
| `data/rozvrh.csv` | `tools/rozvrh.py` | Rozvrhové bloky zvoleného semestru + sloupec `vybrano` |
| `data/ucitele.csv` | `tools/rozvrh.py` | Kdo v tom semestru reálně učí (`kod, ucitel, role`) |
| `data/anotace.csv` | `tools/anotace.py` | Anotace, sylabus, podmínky zakončení, literatura |
| `data/listky.csv` | `tools/listky.py` | Jazyk výuky a kapacita jednotlivých paralelek |
| `data/anketa_cisla.csv` | `tools/anketa.py` | Číselné hodnocení po letech a vyučujících |
| `data/anketa_komentare.csv` | `tools/anketa.py` | Volné připomínky studentů |
| `data/anketa_souhrn.csv` | `tools/prehled_anket.py` | Průměr na dvojici předmět + vyučující, jen aktuální semestr |
| `data/ucitele_historie.csv` | `tools/ucitele_historie.py` | Kdo předmět učil a **ve kterých letech** + příznak, jestli učí i teď |
| `data/vyklad_zs.csv`, `vyklad_ls.csv` | **agent** | Sylabus a podmínky zakončení přepsané do odrážek |
| `data/anketa_shrnuti.csv` | **agent** | Plusy a minusy na dvojici vyučující + role |
| `data/anketa_predmet.csv` | **agent** | Co anketa říká o předmětu jako takovém, nezávisle na vyučujícím |
| `data/stranky.csv` | **agent** | Docházka, nahrávky, jak se dělá zápočet — ze stránek kurzů, s citací |
| `data/tagy.csv` | **agent** | Tematické oblasti předmětu pro filtrování na stránce |
| `data/szz_temata.csv` | **agent** | Požadavky SZZ okruhů rozepsané na atomická témata |
| `data/szz_pokryti.csv` | **agent** | Téma × předmět + síla pokrytí + citace ze sylabu |

Agentní soubory mají vlastní návod v `agentni-vrstva.md`.

## Obnovení dat

```bash
python3 tools/sis.py              # data/sis.csv pro všechny kódy z predmety.csv
python3 tools/sis.py NPFL140      # jen vypíše detail jednoho předmětu, nic nezapíše
python3 tools/rozvrh.py           # rozvrh výchozího (zimního) semestru
python3 tools/rozvrh.py --sem 2   # letní semestr
python3 tools/rozvrh.py --obnovit # znovu stáhne, nečte cache
python3 tools/anotace.py
python3 tools/listky.py
python3 tools/anketa.py           # trvá nejdéle, klidně na pozadí
python3 tools/anketa.py --obnovit
python3 tools/ucitele_historie.py
```

Stažené HTML a CSV se cachuje v `zdroje/` — ta složka **není v gitu**, každý si ji
natáhne sám. Bez `--obnovit` se ze SIS znovu nestahuje nic, co už v cache je,
takže opakované spuštění je zadarmo.

Odvozené přehledy:

```bash
python3 tools/render.py           # -> 10-predmety-tabulka.md (bilance kreditů!)
python3 tools/prehled_rozvrhu.py  # -> 11-rozvrh-ZS.md
python3 tools/prehled_anket.py    # -> 12-ankety-prehled.md + data/anketa_souhrn.csv
python3 tools/artifact.py         # -> artifact/plan.html
```

## Nový semestr / nový akademický rok

1. `data/program.json` → `semestr.skr` a `semestr.sem` (`1` = zimní, `2` = letní).
2. `python3 tools/rozvrh.py --obnovit`, pak `tools/listky.py`.
3. `tools/prehled_rozvrhu.py`, `tools/artifact.py`, znovu publikovat.

Rozvrh bývá dlouho označený jako předběžný („v působnosti rozvrhové komise") —
před zápisem ho vždycky přetáhni znovu.

## Na co si dát pozor

- **`stav` v `data/sis.csv`.** Předmět může být v SIS veden jako „nevyučován" a mít
  přitom kompletní anotaci. Takový předmět do plánu nepatří. Kontroluj to u každého
  nového kandidáta.
- **Předmět bez rozvrhového lístku s časem** znamená obvykle výuku po domluvě
  s vyučujícím, ne chybu ve scraperu. Napiš to jako informaci.
- **Připomínka v anketě vedená u předmětu jako celku** má v `anketa_komentare.csv`
  prázdný sloupec `vyucujici`. Nepřiřazuj ji nikomu.
- **Ankety se stahují pro všechny předměty v `predmety.csv`**, i pro vyřazené
  (vrstva `X`) — jinak nejde doložit, proč byly vyřazené.
