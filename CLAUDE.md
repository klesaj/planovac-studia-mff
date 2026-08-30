# Claude Code — plánovač magisterského studia MFF UK

## Co to je

Plánovací aparát pro navazující magisterské studium na MFF UK. Drží katalog předmětů
s daty ze SIS (rozvrh, ankety, anotace, docházka), hlídá kreditová minima a pokrytí
státnicových okruhů a generuje interaktivní stránku, ve které si student klikáním
sestaví plán i konkrétní rozvrh.

**Kompletní návod je ve skillu `planovac-studia`** (`.claude/skills/planovac-studia/`).
Načti ho, jakmile se má v repu cokoli dělat s předměty, rozvrhem, státnicemi nebo
daty ze SIS. Tenhle soubor je jen rozcestník.

## Jak navázat

1. Zjisti, jestli je repo nastavené:
   `python3 -c "import json;print(json.load(open('data/program.json'))['_nastaveno'])"`
   Když `False`, jde o první spuštění → skill `planovac-studia`, sekce „První spuštění".
2. Přečti `README.md` a `10-predmety-tabulka.md` (aktuální bilance kreditů a plán).
3. Data v `data/*.csv` jsou stažená ze SIS. **Netahej je znovu**, pokud o to student
   nepožádá nebo neuplynul čas — rozvrh se během léta ještě mění.

## Nedotknutelná pravidla

1. **Nic nevymýšlej.** Kódy předmětů, kredity, semestry, vyučující a neslučitelnosti
   se berou ze SIS, skupiny předmětů a kreditová minima z Karolinky. Když si nejsi
   jistý: `python3 tools/sis.py <KOD>`.
2. **Chybějící data nedoplňuj z jiného ročníku.** „SIS to zatím nevypsal" je informace,
   ne díra k zaplácnutí.
3. **O semestrech rozhoduje student, ne ty ani skripty.** Sloupec `plan_semestr`
   v `data/predmety.csv` je jeho rozhodnutí. Navrhuj a kontroluj, zapisuj až po schválení.
4. **Generované soubory needituj ručně.** Seznam je ve skillu. Změna = změna vstupního
   CSV a spuštění skriptu.
5. **U docházky (`data/stranky.csv`) je odhad zakázaný.** Ke každému tvrzení doslovná
   citace zdroje, jinak `nezjisteno`. Falešné „docházka se neřeší" stojí zápočet.
6. **Studijní plán se rok od roku mění.** Předvyplněná data stojí na Karolince
   2025/2026. Před zápisem se čísla musí překontrolovat. Tenhle disclaimer nemaž.
7. **Píše se česky, věcně, tabulky nad odstavce.**

## Kam co ukládat

| Cesta | Obsah |
|---|---|
| `data/` | Normalizovaná data s pevnou hlavičkou — jediné, co se čte skripty |
| `dokumenty/` | Výtahy z předpisů (pravidla studia, diplomka a SZZ, prodloužení studia) |
| `zdroje/` | Cache scraperů: stažené HTML ze SIS, CSV rozvrhů, ankety, výtahy stránek kurzů. **Není v gitu**, natáhne se sama |
| `artifact/plan.html` | Generovaná stránka, publikuje se jako Artifact na stále stejnou cestu |
| `tools/` | Scrapery a generátory. `program.py` je loader konfigurace |

Surové stažené soubory patří do `zdroje/`, nikdy ne do `data/`.

## Struktura dat

Ruční (rozhodnutí studenta): `data/program.json`, `data/predmety.csv`,
`data/relevance.csv`, `data/rozvrh_vyber.csv`, `data/ankety.csv`.

Scrapované: `sis.csv`, `rozvrh.csv`, `ucitele.csv`, `anotace.csv`, `listky.csv`,
`anketa_cisla.csv`, `anketa_komentare.csv`, `anketa_souhrn.csv`, `ucitele_historie.csv`.

Psané agentem (zjednodušují, ale nesmí měnit fakta): `vyklad_zs.csv`, `vyklad_ls.csv`,
`anketa_shrnuti.csv`, `anketa_predmet.csv`, `stranky.csv`, `tagy.csv`,
`szz_temata.csv`, `szz_pokryti.csv`.

Podrobnosti u každého souboru: `.claude/skills/planovac-studia/references/`.
