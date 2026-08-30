---
name: planovac-studia
description: Plánovač magisterského studia na MFF UK. Použij vždy, když se v tomhle repu má cokoli dělat s výběrem předmětů, rozvrhem, státnicemi nebo daty ze SIS - od prvního nastavení (kdo jsem, jaký program a zaměření) přes stažení dat ze SIS a anket až po sestavení plánu a publikaci interaktivní stránky. Spouštěj i při dotazech typu "co si mám zapsat", "vejde se mi to do rozvrhu", "chybí mi kredity", "přidej předmět X", "je tenhle předmět dobrý".
---

# Plánovač studia MFF UK

Tenhle repozitář je plánovací aparát pro navazující magisterské studium na MFF UK:
katalog předmětů se všemi daty ze SIS (rozvrh, ankety, anotace, docházka), kontrola
kreditových minim a státnicových okruhů, a interaktivní stránka, ve které si uživatel
klikáním sestaví plán i konkrétní rozvrh.

**Data se nikdy nepřepisují ručně.** Všechno tahají skripty v `tools/` ze SIS, který
je veřejný i bez přihlášení. Ruční jsou jen čtyři soubory, ve kterých je rozhodnutí
uživatele: `data/predmety.csv`, `data/relevance.csv`, `data/rozvrh_vyber.csv`,
`data/ankety.csv`.

## Nejdřív zjisti, jestli je repo už nastavené

```bash
python3 -c "import json;d=json.load(open('data/program.json'));print(d.get('_nastaveno'), d['program'], d['zamereni_aktivni'], d['semestr']['popis'])"
```

Když `_nastaveno` chybí nebo je `false`, jde o **první spuštění** → sekce níž.
Když je `true`, repo je uživatelovo a jedeš rovnou na jeho dotaz.

## První spuštění: nastavení pro nového uživatele

Repo přichází předvyplněné pro program **Informatika – Umělá inteligence**, zaměření
**Strojové učení**, nástup ZS 2026/2027. To je jen výchozí sada, ne doporučení.
Zeptej se **jednou, v jednom kole** (nástroj na otázky, ne pět zpráv za sebou):

1. **Program a zaměření.** Který magisterský program a které zaměření studuje.
   Když neví, nabídni zaměření programu, který si vybral (`data/program.json`,
   klíč `zamereni`) a řekni, že se to dá změnit kdykoli.
2. **Kdy nastupuje** (akademický rok a semestr) — určuje, který rozvrh se tahá.
3. **Jak dlouho chce studovat** — 2 roky standardně, nebo 3 s rozloženým úsekem
   (`dokumenty/03-jak-prodlouzit-studium.md`).
4. **Co ho zajímá** — volně, vlastními slovy. Tohle je vstup pro `data/tagy.csv`
   a pro to, co mu doporučíš.
5. **Jak studuje** — chodí na přednášky, nebo se učí sám a chodí jen tam, kde se
   docházka hlídá? Tohle mění, na co se optimalizuje rozvrh: na hodiny, nebo na
   **počet dní, kdy musí fyzicky být ve škole**.

Pak proveď v tomhle pořadí:

1. **Zapiš odpovědi do `data/program.json`** — `program`, `zamereni_aktivni`,
   `semestr`, a `_nastaveno: true`. Kreditová minima a SZZ okruhy jeho zaměření
   ověř proti Karolince, nevymýšlej je (viz `references/pridani-predmetu.md`).
2. **Doplň nabídku předmětů** na všechny povinné a povinně volitelné jeho programu
   a zaměření — postup v `references/pridani-predmetu.md`. Výchozí sada je vybraná
   pro strojové učení a jinému zaměření bude připadat děravá.
3. **Stáhni data**: `tools/sis.py`, `tools/rozvrh.py`, `tools/anketa.py`,
   `tools/anotace.py`, `tools/listky.py`, `tools/ucitele_historie.py`.
   Trvá to jednotky minut, pusť to na pozadí.
4. **Dopiš agentní vrstvu** pro nově přidané předměty — `references/agentni-vrstva.md`.
5. **Přegeneruj a publikuj stránku** — `references/stranka.md`.

Teprve pak se dá plánovat.

## Běžná práce

| Uživatel chce | Kde je postup |
|---|---|
| přidat předmět / celý program / jiné zaměření | `references/pridani-predmetu.md` |
| aktualizovat data ze SIS, nový semestr rozvrhu | `references/datova-vrstva.md` |
| doplnit sylaby, ankety, docházku u nových předmětů | `references/agentni-vrstva.md` |
| přegenerovat a publikovat stránku | `references/stranka.md` |
| sestavit nebo zkontrolovat plán | níž, „Jak sestavit plán" |

## Jak sestavit plán

Plán je sloupec `plan_semestr` v `data/predmety.csv`: `ZS1`, `LS1`, `ZS2`, `LS2`,
`ZS3`, `LS3`. Prázdno = předmět se jen zvažuje.

**Rozhodnutí o semestrech patří uživateli, ne tobě ani skriptům.** Ty navrhuješ
a kontroluješ; zapisuješ, až to schválí.

Co musí sedět, a po každé změně to znovu přepočítej:

- **Kreditová minima po skupinách** (`data/program.json` → `minima`). Skupiny se
  nesmí míchat, jsou to oddělené kbelíky. Součty i celkových 120 ověř skriptem:
  `python3 tools/render.py` vypíše bilanci do hlavičky `10-predmety-tabulka.md`.
- **Průběžné kontroly studia** (`kontroly` v konfiguraci): typicky 45 kreditů po
  prvním roce a 90 po druhém. Sečti kredity semestrů ZS1+LS1 a ZS1..LS2.
- **Semestr výuky.** Předmět z `data/sis.csv` se sloupcem `semestr` = `zimní`
  nesmí být v `LS*` a naopak. Časté a snadno přehlédnutelné.
- **Neslučitelnosti** (`neslucitelnost` v `data/sis.csv`) — proti sobě navzájem
  i proti tomu, co má uživatel z bakaláře.
- **Pokrytí státnicových okruhů** — `data/szz_temata.csv` × `data/szz_pokryti.csv`.
  Díru hlas jako díru, nezakrývej ji předmětem, který téma jen ťukne.
- **Docházka** (`data/stranky.csv`). U předmětů s `povinna` nebo `bodovana` musí
  uživatel na cvičení reálně chodit — když se učí samostudiem, je to ta jediná věc,
  která mu vynucuje dny ve škole. Nedávej takové předměty do jednoho semestru víc,
  než unese.
- **Rozvrhové kolize** v semestrech, pro které SIS rozvrh vypsal.

Až plán sedí, **řekni to čísly a stručně**: kredity po skupinách proti minimům,
kontroly po ročnících, pokrytí okruhů, kolik dní v týdnu musí být ve škole.
Ne vyprávěním.

## Tvrdá pravidla

1. **Nikdy nevymýšlej kódy, kredity, semestry ani vyučující.** Když si nejsi jistý,
   ověř v SIS: `python3 tools/sis.py <KOD>` nebo
   `curl -s "https://is.cuni.cz/studium/predmety/index.php?do=predmet&kod=<KOD>"`.
2. **Chybějící data v SIS nikdy nedoplňuj z jiného ročníku.** Když SIS rozvrh na
   příští semestr nevypsal, je to informace („SIS to zatím nevypsal"), ne díra k zaplácnutí.
3. **Needitovuj generované soubory**: `10-predmety-tabulka.md`, `11-rozvrh-ZS.md`,
   `12-ankety-prehled.md`, `artifact/plan.html`, `data/sis.csv`, `data/rozvrh.csv`,
   `data/ucitele*.csv`, `data/anketa_*.csv` (kromě `ankety.csv`), `data/anotace.csv`,
   `data/listky.csv`. Změna = změna vstupu a spuštění skriptu.
4. **Hláška na webové stránce není důkaz, že data nejsou.** SIS umí tvrdit „rozvrh
   zatím není zveřejněn" a přitom ho mít v CSV exportu. Ověřuj na exportu.
5. **Anketa je vstup, ne závěr.** Připomínky vedené u garanta se často týkají jiného
   vyučujícího téhož předmětu. Přiřazení ověřuje uživatel, jeho ověřený závěr patří
   do `data/ankety.csv`. Ty tvrď jen to, co v datech opravdu je, a vždy s počtem
   respondentů.
6. **Studijní plány se mění.** Předvyplněná data stojí na Karolince 2025/2026.
   Než uživatel jde k zápisu, čísla se musí překontrolovat proti aktuální Karolince.
   Tenhle disclaimer nemaž.
7. **Píše se česky, věcně, tabulky nad odstavce.**
