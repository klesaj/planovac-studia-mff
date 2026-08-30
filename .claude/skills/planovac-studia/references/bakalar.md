# Výpis z bakaláře: načtení a co z něj plyne

Co student absolvoval v bakaláři, **nezjistíš ze SIS sám** — je to za přihlášením.
Musí ti dát výpis. Je to ale jediný vstup, který ti dovolí spolehlivě hlídat
neslučitelnosti, takže o něj popros hned při nastavení.

## Jak ho student sežene

V SIS: **Výsledky zkoušek – prohlížení → Studijní mezivýsledky → tisk**.
Vypadne PDF s pevným rozvržením sloupců. Stačí ho hodit do repa (klidně do
`zdroje/`, ta složka není v gitu, takže nikam neodejde).

## Načtení

```bash
python3 tools/absolvovane.py vypis.pdf     # -> data/absolvovane.csv
python3 tools/absolvovane.py vypis.txt     # když už je převedený pdftotext -layout
```

Parser potřebuje `pdftotext` (balík `poppler-utils`). Výsledek je
`kod, nazev, examinace, typ_v_bc, kredity, stav, znamka, datum, rok`.

**Součty si po načtení ověř proti poslednímu řádku výpisu** („Získané kredity za
povinné/povinně volitelné/volitelné"). Když nesedí, layout PDF se v novější verzi
SIS posunul — řekni to studentovi a zbytek dodělej ručně, ale **nikdy si čísla
nedomýšlej**. Předměty zapsané dvakrát v různých letech (typicky tělocviky) jsou
ve výpisu dvakrát správně, nesluč je.

`data/absolvovane.csv` **není v gitu vyplněný** a být nemá — je to osobní údaj.
Když repo někomu předáváš dál, smaž ho.

## Kontrola proti plánu

```bash
python3 tools/absolvovane.py --kontrola
```

Vypíše čtyři věci:

1. **Předměty z nabídky neslučitelné s tím, co už má splněné** — ty si zapsat nejde,
   tečka. Nejčastější tichá past celého plánování.
2. **Předměty, které už má splněné** a přesto jsou v nabídce.
3. **Předměty zapsané a nesplněné** — ty jde zapsat znovu. Občas jde o hotovou práci,
   která jen nemá zápis; zeptej se, jestli u některého takového nemá domluvu
   s vyučujícím.
4. **Bilanci kreditů podle typu v bakaláři** — podklad k žádosti o uznání.

Když je výpis načtený, promítne se to i na stránku: dlaždice dostane chip
(„neslučitelný s Bc.", „už máš splněný", „z Bc. nedokončený") a v detailu je proužek
s vysvětlením. Bez výpisu se nic z toho nezobrazuje.

## Uznávání kreditů z bakaláře

Tohle je místo, kde se nejsnáz vzbudí falešná naděje. Pravidla:

- Uznat jde **jen předmět, který v bakaláři přebyl** nad kredity potřebné k jeho
  dokončení (180) — a **jen ve skupině, kde ten přebytek reálně vznikl**. Když
  povinné a povinně volitelné dohromady nedosáhnou 180 a zbytek dorovnaly volitelné,
  pak jsou uznatelné **jen volitelné** předměty.
- Musí být splněný **nejvýše 4 roky zpět** a hodnocený výborně nebo velmi dobře.
- Musí **„sylabem a úrovní odpovídat příslušnému stupni studia"**. Na tomhle padají
  čistě bakalářské předměty, jazyky a tělocviky, i když formálně sedí.
- Rozhoduje **garant programu**, ne studijní oddělení.

Praktický důsledek: plán **nesmí stát na horní hranici** toho, co by šlo uznat.
Spočítej variantu bez uznání a řekni, o kolik kreditů jde. A doporuč podat žádost
hned na začátku, ne až před kontrolou po prvním roce.

Od 1. 10. 2026 platí nový SZŘ UK (uznávání v čl. 33–36) a nová Pravidla MFF
s přepsaným čl. 12 — než budeš citovat čísla článků, ověř si aktuální znění.

## Předměty s hotovou prací bez zápisu

Zvláštní případ, který stojí za doptání: student předmět v bakaláři **zapsaný měl,
splnil ho, ale známka se nestihla zapsat**. Uznat to nejde (v SIS není hodnocení),
ale předmět **jde zapsat znovu** a vyučující zápis obvykle dořeší. Ve výpisu se to
tváří jako „nesplněno", takže to `--kontrola` vypíše — a je to jediné místo, kde
„nesplněno" může znamenat téměř hotové kredity.
