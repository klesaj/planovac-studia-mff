# První spuštění: runbook od nuly k hotové stránce

Tohle je postup pro **nového uživatele s čerstvě naklonovaným repem**
(`_nastaveno: false` v `data/program.json`). Data, která v repu jsou, patří někomu
jinému — zaměření Strojové učení. Než je uživatel začne brát za svoje, musí se
nabídka dotáhnout na jeho program.

Celé to trvá **desítky minut až pár hodin**, podle toho, kolik předmětů přibude.
Řekni to dopředu a průběžně hlas, kde jsi. Nezastavuj se v půlce a neptej se
„mám pokračovat?" — postup je daný, ptej se jen na to, co je vážně rozhodnutí
uživatele.

---

## Krok 0 — zeptej se, jednou a najednou

Jedno kolo otázek, ne pět zpráv za sebou. Co potřebuješ, je v SKILL.md v sekci
„První spuštění". Kritické jsou tři věci, které nedokážeš zjistit sám:

- **program a zaměření** — určuje celou nabídku,
- **jak studuje** (chodí × samostudium) — určuje, na co se optimalizuje rozvrh,
- **výpis z bakaláře** — bez něj neumíš hlídat neslučitelnosti (`bakalar.md`).

Když výpis nedodá hned, pokračuj bez něj a připomeň se později. Není to blokující.

## Krok 1 — konfigurace programu

`data/program.json`: `program`, `zamereni_aktivni`, `semestr`, `minima`, `zamereni`,
`okruhy`, `oblasti`. Čísla a okruhy **ověř proti Karolince**, nevymýšlej je —
postup v `pridani-predmetu.md`. Nakonec `_nastaveno: true`.

`oblasti` je slovník tematických chipů pro filtrování. Výchozí sada je pro umělou
inteligenci; pro softwarové systémy, teoretickou informatiku nebo vizuální výpočty
ji přepiš, jinak budou chipy nesmyslné.

## Krok 2 — nabídka předmětů

Doplň `data/predmety.csv` na **všechny povinné a povinně volitelné** programu
a zaměření (`pridani-predmetu.md`). Nešetři: chybějící předmět je horší než
přebývající, protože uživatel nevidí, co nevidí.

Do `data/relevance.csv` přidej ke **každému** předmětu `kod, zkratka` — lidský
název. Stránka mluví názvy, ne kódy; bez tohohle bude všude syrový název ze SIS.
Sloupec `relevance` nech prázdný, dokud uživatel neřekne, co ho na předmětu zajímá.

## Krok 3 — scrapery

Pusť na pozadí, je to nejdelší část a nevyžaduje tvou pozornost:

```bash
python3 tools/sis.py && python3 tools/anotace.py && python3 tools/listky.py \
  && python3 tools/rozvrh.py && python3 tools/anketa.py \
  && python3 tools/ucitele_historie.py
```

Až doběhne, zkontroluj `data/sis.csv`: předměty se stavem **„nevyučován"** přesuň
do vrstvy `X` s důvodem. Předmět s prázdným názvem znamená špatný kód.

## Krok 4 — agentní vrstva (tady vzniká ta kvalita)

Bez tohohle kroku je stránka jen hezčí SIS. Pravidla a formáty jsou
v `agentni-vrstva.md`; tady je pořadí a rozvržení práce.

Rozděl předměty do dávek po zhruba osmi a pusť na ně agenty **paralelně**. Jeden
agent = jedna dávka a **jeden soubor**, ne všechny soubory k jednomu předmětu —
míchání formátů v jedné hlavě je nejčastější zdroj chyb. Pořadí podle užitečnosti:

1. **`stranky.csv`** — docházka a reálnost samostudia. Nejdražší a nejcennější,
   protože tohle SIS neříká a rozhoduje to o celém rozvrhu. Jak sehnat zdroje
   je v `agentni-vrstva.md`, sekce „Jak najít stránku kurzu".
2. **`vyklad_zs.csv` / `vyklad_ls.csv`** — sylabus a podmínky do odrážek
   z `data/anotace.csv`. Nepotřebuje web, jen pečlivost u čísel.
3. **`tagy.csv`** — rychlé, ale bez něj nejdou filtrovat dlaždice.
4. **`anketa_predmet.csv`** a **`anketa_shrnuti.csv`** — z `anketa_komentare.csv`.
5. **`szz_temata.csv`** + **`szz_pokryti.csv`** — až nakonec, potřebují hotové
   sylaby i znění okruhů z Karolinky.

Po každé dávce **přeměř vzorek proti zdroji**, zvlášť čísla (body, procenta, váhy
známky, počty respondentů). Nález agenta neber automaticky: když hlásí chybu
s číslem, ověř i doklad, ne jen směr tvrzení.

## Krok 5 — kontrola proti bakaláři

Když je výpis načtený:

```bash
python3 tools/absolvovane.py --kontrola
```

Neslučitelné předměty přesuň do vrstvy `X` s důvodem. Podrobnosti v `bakalar.md`.

## Krok 6 — stránka

```bash
python3 tools/render.py && python3 tools/prehled_rozvrhu.py \
  && python3 tools/prehled_anket.py && python3 tools/artifact.py
```

`artifact.py` píše varování na stderr — **přečti si je**, hlásí předměty s neznámou
skupinou, které by z dlaždic tiše zmizely. Pak stránku publikuj a **dej uživateli
odkaz** (`stranka.md`).

---

## Kdy je nastavení hotové

Projeď tenhle seznam a co nesedí, dodělej. Nehlas hotovo, dokud neprojde:

```bash
python3 - <<'PY'
import csv, json, os
d = json.load(open('data/program.json'))
p = list(csv.DictReader(open('data/predmety.csv', encoding='utf-8')))
zive = [r for r in p if r['vrstva'] in 'ABC']
kody = {r['kod'] for r in zive}
def pokryti(f, sl='kod'):
    if not os.path.exists('data/' + f): return set()
    return {r[sl] for r in csv.DictReader(open('data/' + f, encoding='utf-8')) if r.get(sl)}
rel = {r['kod'] for r in csv.DictReader(open('data/relevance.csv', encoding='utf-8'))
       if r['zkratka'].strip()}
print('nastaveno            ', d.get('_nastaveno'))
print('předmětů v nabídce   ', len(zive))
print('bez lidského názvu   ', sorted(kody - rel) or 'nic')
for f in ['sis.csv', 'anotace.csv', 'stranky.csv', 'tagy.csv', 'anketa_predmet.csv']:
    chybi = kody - pokryti(f)
    print(f'{f:22} chybí u {len(chybi):3} předmětů', sorted(chybi)[:5] or '')
chybi = kody - pokryti('vyklad_zs.csv') - pokryti('vyklad_ls.csv')
print(f'{"vyklad_zs+ls.csv":22} chybí u {len(chybi):3} předmětů', sorted(chybi)[:5] or '')
print('SZZ témat            ', len(pokryti('szz_temata.csv', 'tema')))
print('výpis z bakaláře     ', 'ano' if os.path.exists('data/absolvovane.csv') else 'NE')
PY
```

- `_nastaveno` je `true`
- žádný předmět bez lidského názvu v `relevance.csv`
- `sis.csv` a `anotace.csv` pokrývají **všechny** předměty
- `stranky.csv`, `tagy.csv`, `vyklad_*` pokrývají všechny (u `stranky.csv` je
  legitimní `nezjisteno`, ale řádek tam být musí)
- `szz_temata.csv` má témata pro **všechny okruhy aktivního zaměření**
- `artifact.py` neplive varování o neznámé skupině
- stránka je publikovaná a uživatel má odkaz

Co nevyšlo, **řekni nahlas** — u kterých předmětů se nepodařilo najít stránku kurzu,
které téma státnic nepokrývá nic, co je v SIS prázdné. Díra, o které uživatel ví,
je použitelná; díra, kterou jsi zamluvil, ho stojí zápočet.
