# Přidání předmětů, programů a zaměření

## Jeden předmět

1. Ověř kód v SIS: `python3 tools/sis.py <KOD>`. Když se nevypíše název, kód neexistuje.
2. Přidej řádek do `data/predmety.csv`:
   - `vrstva` — `A` doporučeno studijním plánem, `B` vlastní jádro uživatele,
     `C` kandidát, `X` nedostupný (nevyučovaný, neslučitelný) s důvodem v `poznamka`
   - `zamereni` — kód zaměření, víc oddělených `|`, nebo `vse` pro předmět společný
     celému programu. Podle tohohle se filtruje na stránce.
   - `skupina` — `povinny` / `profilujici` / `rozsirujici` / `volitelny` **podle
     studijního plánu programu**, ne podle dojmu. Skupiny se nesmí míchat.
   - `szz` — kód státnicového okruhu, nebo `-`
   - `plan_semestr` — nech prázdné, o semestru rozhoduje uživatel
   - `poznamka` — věcně: neslučitelnosti, stav v SIS, rozsah, co je na předmětu zvláštní.
     Ne osobní hodnocení.
3. `python3 tools/sis.py && python3 tools/anotace.py && python3 tools/listky.py`
4. `python3 tools/rozvrh.py` a `python3 tools/anketa.py` (nové předměty si dotáhnou samy)
5. `python3 tools/ucitele_historie.py`
6. Dopiš agentní vrstvu pro ten předmět — `agentni-vrstva.md`
7. `python3 tools/render.py && python3 tools/artifact.py`, publikuj

Do `data/relevance.csv` přidej `kod, zkratka` — **lidský název** předmětu, protože
stránka mluví názvy, ne kódy. Sloupec `relevance` je volitelný odstavec „proč to chci";
nech ho prázdný, dokud uživatel neřekne, co ho na předmětu zajímá.

## Celý program nebo jiné zaměření

Výchozí sada v repu je vybraná pro zaměření Strojové učení. Pro kohokoli jiného
je děravá, a **chybějící předmět je horší než přebývající** — uživatel nevidí, co
nevidí. Proto při nastavení pro nového člověka nabídku vždycky dotáhni.

### 1. Sežeň oficiální seznam

Zdroj je studijní plán programu v **Karolince** (ne wikipedie, ne dohady):

```bash
curl -sL "https://www.mff.cuni.cz/cs/studenti/bakalarske-a-magisterske-studium/karolinka" -o zdroje/karolinka.html
```

Když se odkaz změnil, hledej „Karolinka" na `mff.cuni.cz` a stáhni PDF svazku
**Informatika – navazující magisterské studium**. Text z něj vytáhni
`pdftotext -layout`. Ve studijním plánu programu najdeš:

- povinné předměty programu,
- povinně volitelné po skupinách (profilující / rozšiřující) a jejich minima,
- zaměření a jejich státnicové okruhy s doporučenými předměty.

Alternativně jde nabídka projít v SIS podle pracoviště (KTIML `32-KTIML`,
ÚFAL `32-UFAL`, KSI `32-KSI`, KAM/KTI, KPMS) — ale skupinu předmětu (profilující ×
rozšiřující) SIS **neříká**, tu má jen Karolinka. Nehádej ji.

### 2. Zapiš to do konfigurace

`data/program.json`:

- `minima` — kreditová minima skupin daného programu
- `zamereni` — každé zaměření: `nazev`, `garant`, seznam kódů `okruhy`
- `okruhy` — každý okruh: `nazev` a `doporucene` (kódy předmětů ze studijního plánu)
- `zamereni_aktivni` — které zaměření uživatel studuje

Kódy okruhů si vymýšlíš ty (krátká zkratka), ale musí být **unikátní napříč všemi
zaměřeními**, protože se používají v `data/szz_temata.csv` a `data/predmety.csv`.

### 3. Doplň předměty a data

Přidej všechny povinné a povinně volitelné programu do `data/predmety.csv`
(vrstva `A` pro to, co studijní plán u okruhů přímo doporučuje, jinak `C`),
se správným `zamereni`. Pak projeď celý řetěz skriptů z `datova-vrstva.md`
a agentní vrstvu.

### 4. Státnicové okruhy

Znění požadavků okruhů je v Karolince u zaměření. Rozepiš ho na atomická témata
do `data/szz_temata.csv` a napároj na předměty do `data/szz_pokryti.csv` —
postup v `agentni-vrstva.md`. Bez tohohle stránka spadne zpátky na hrubé počítání
doporučených předmětů a kontrola pokrytí je k ničemu.

## Co do nabídky nepatří

- Předmět se stavem **„nevyučován"** v SIS → vrstva `X` s důvodem, ne do plánu.
- Předmět **neslučitelný** s něčím, co má uživatel splněné z bakaláře. Neslučitelnost
  je v `data/sis.csv`, ale co má uživatel z bakaláře, víš jen od něj — zeptej se,
  než něco doporučíš.
- Předmět z **jiné fakulty nebo jiné oblasti vzdělávání**, který se do skupin
  programu vůbec nepočítá. Ověř v Karolince, jestli se dá zapsat jako volitelný.

Když předmět zamítáš, **zapiš ho stejně** — s vrstvou `X` a důvodem v poznámce.
Kandidát, který v `predmety.csv` není, je neviditelný: nezobrazí se na stránce,
nestáhne se mu anketa, a za půl roku ho nikdo nedohledá.
