# Plánovač magisterského studia na MFF UK

Nástroj, který ti pomůže vybrat předměty na navazující magisterské studium na Matfyzu
a poskládat je do semestrů tak, aby to vyšlo kreditově, státnicově i rozvrhově.

Není to statická tabulka. Je to **repozitář, který se ovládá přes Claude Code**:
řekneš mu, co studuješ a co tě zajímá, on si sám dotáhne data ze SIS (rozvrh, anotace,
studentské ankety, podmínky zápočtu) a vyrobí interaktivní stránku, ve které si
klikáním sestavíš plán i konkrétní rozvrh.

## Co to umí

- **Katalog předmětů** s tím, co o nich SIS ví: kredity, rozsah, semestr, vyučující,
  neslučitelnosti, anotace, sylabus, podmínky zakončení.
- **Studentské ankety** stažené a shrnuté — u každého vyučujícího zvlášť, včetně toho,
  ve kterých letech předmět učil a jestli se hodnocení v čase změnilo.
- **Docházka a reálnost samostudia** — ze stránek kurzů, u každého tvrzení citace.
  Tohle SIS neříká a přitom to rozhoduje o tom, kolik dní v týdnu musíš být ve škole.
- **Kontrola plánu** — kreditová minima po skupinách, průběžné kontroly po ročnících,
  pokrytí státnicových okruhů po jednotlivých tématech, rozvrhové kolize.
- **Interaktivní stránka** — týdenní mřížka, dlaždice předmětů s filtrem podle zaměření
  a oblasti, plánovací režim a stavba rozvrhu klikáním do mřížky.

## Jak to rozjet

Potřebuješ [Claude Code](https://claude.com/claude-code) a Python 3.

```bash
git clone <adresa-tohohle-repa> studijni-plan
cd studijni-plan
claude
```

A pak prostě napiš, co chceš. Například:

> Chci si naplánovat magistra. Program Informatika – Umělá inteligence, zaměření
> Inteligentní agenti, nastupuju v ZS 2026/27.

Claude si načte skill `planovac-studia`, doptá se na zbytek (jak dlouho chceš studovat,
co tě zajímá, jestli chodíš na přednášky) a dál si poradí sám: dotáhne nabídku předmětů
tvého programu, stáhne data ze SIS a vygeneruje stránku.

**Počítej s desítkami minut až pár hodinami.** Stažení dat ze SIS je otázka minut,
ale to samo o sobě vyrobí jen hezčí SIS. Ta užitečná část — docházka vytažená ze
stránek kurzů, sylaby přepsané do odrážek, shrnuté ankety, pokrytí státnic po
tématech — je práce, kterou dělá Claude, ne skript. Nech ho to doběhnout;
ve skillu má kontrolní seznam, podle kterého pozná, že je hotový.

### Co je předvyplněné

Repo přichází s daty pro program **Informatika – Umělá inteligence**, zaměření
**Strojové učení**, semestr **ZS 2026/2027** — 60 předmětů se staženými anketami,
anotacemi, rozvrhem a docházkou. Je to výchozí sada, ne doporučení. Pro jiné zaměření
si nech nabídku dotáhnout, výchozí by ti připadala děravá.

Ve `data/predmety.csv` je sloupec `zamereni`; podle něj se dá na stránce filtrovat.
Předmět označený `vse` je společný celému programu a filtrem nezmizí.

Přibalená data nejsou všude stejně hluboká. Ze SIS je staženo **všechno u všech**
předmětů (anotace, sylaby, rozvrh, ankety). Vrstva, kterou píše agent, je hotová
u jádra a chybí u předmětů, které byly na okraji původního výběru:

| Vrstva | Pokryto |
|---|---|
| Data ze SIS (`sis`, `anotace`, `rozvrh`, `ankety`) | všech 56 |
| Sylabus a podmínky v odrážkách (`vyklad_*`) | 42 z 56 |
| Docházka a samostudium (`stranky`) | 40 z 56 |
| Oblasti pro filtrování (`tagy`) | 50 z 56 |
| Shrnutí anket k předmětu (`anketa_predmet`) | 17 z 56 |
| Pokrytí státnic (`szz_*`) | 37 témat zaměření Strojové učení |

Claude to umí doplnit — a při nastavení pro nového uživatele to udělá sám,
podle kontrolního seznamu ve skillu.

## Co s tím dál

Pár věcí, na které se vyplatí Clauda zeptat:

- „Vejde se mi ZS do dvou dnů v týdnu?"
- „Kolik mi chybí do kreditového minima profilujících?"
- „Který státnicový okruh mám nejhůř pokrytý?"
- „Je NAIL002 podle ankety dobrý předmět, nebo si to jen myslím?"
- „Přidej mi do nabídky NPFL138 a řekni, jestli se dá dát samostudiem."

## Struktura

| Cesta | Co v ní je |
|---|---|
| `data/` | Všechna data v CSV — jediné, co skripty čtou |
| `data/program.json` | Konfigurace: program, zaměření, kreditová minima, státnicové okruhy |
| `data/predmety.csv` | **Tvůj výběr** — které předměty sleduješ a v jakém semestru je chceš |
| `tools/` | Scrapery SIS a generátory přehledů a stránky |
| `dokumenty/` | Výtahy z předpisů: pravidla studia, diplomka a státnice, prodloužení studia |
| `artifact/plan.html` | Vygenerovaná stránka (publikuje se jako Artifact) |
| `10-predmety-tabulka.md` | Generovaná přehledovka: bilance kreditů, plán po semestrech, detail předmětů |
| `11-rozvrh-ZS.md` | Rozvrh ze SIS, den po dni a po předmětech |
| `12-ankety-prehled.md` | Ankety ke všem sledovaným předmětům |
| `.claude/skills/planovac-studia/` | Návod pro Clauda — jak se v tom všem pracuje |

Ručně se mění hlavně **`data/predmety.csv`**, ne generované soubory.

## Ruční ovládání (když nechceš Clauda)

```bash
python3 tools/sis.py              # data předmětů ze SIS
python3 tools/sis.py NPFL140      # rychlý detail jednoho předmětu
python3 tools/rozvrh.py           # rozvrh -> data/rozvrh.csv
python3 tools/anotace.py          # anotace, sylaby, podmínky
python3 tools/listky.py           # jazyk výuky a kapacity paralelek
python3 tools/anketa.py           # studentské ankety
python3 tools/ucitele_historie.py # kdo předmět učil a kdy
python3 tools/render.py           # -> 10-predmety-tabulka.md
python3 tools/prehled_rozvrhu.py  # -> 11-rozvrh-ZS.md
python3 tools/prehled_anket.py    # -> 12-ankety-prehled.md
python3 tools/artifact.py         # -> artifact/plan.html
```

Stažené HTML se cachuje v `zdroje/` (není v gitu), takže opakované spuštění nic nestahuje.

## Zdroje a jejich platnost

Data pocházejí z veřejné části SIS (`is.cuni.cz`), která nevyžaduje přihlášení,
a z Karolinky MFF UK. **Kreditová minima a skupiny předmětů jsou z Karolinky
2025/2026** a rok od roku se mění — než půjdeš k zápisu, nech si je překontrolovat
proti aktuálnímu vydání. Rozvrh bývá až do začátku semestru předběžný.

Nic z toho nenahrazuje studijní oddělení ani garanta programu. Je to nástroj,
jak si udělat pořádek v tom, co si vlastně chceš zapsat.
