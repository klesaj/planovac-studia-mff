# Agentní vrstva: co píšeš ty, ne scraper

Šest CSV nevzniká scrapováním — píše je agent ze surových zdrojů. Platí u nich
**jedno tvrdé pravidlo: smíš zjednodušovat, nesmíš měnit fakta.** Původní text ze SIS
zůstává na stránce schovaný pod `<details>` a přes proklik do SIS, aby to šlo kdykoli
ověřit.

Kde nejsnáz vzniká chyba: **čísla**. Body, procenta, váhy známky, počty úkolů,
respondenty. Každé číslo, které do těchhle souborů napíšeš, si najdi ve zdroji
a porovnej znak po znaku. Nedopočítávej, nezaokrouhluj, nesluč dvě položky do jedné.

Víchodnotové sloupce (`temata`, `zapocet`, `zkouska`, `pozor`, `plus`, `minus`, `tagy`)
jsou položky oddělené znakem `|` bez mezer okolo.

---

## `vyklad_zs.csv`, `vyklad_ls.csv` — sylabus a zakončení v odrážkách

`kod,temata,zapocet,zkouska,pozor,delka_puvodni`

Zdroj: `data/anotace.csv` (sloupce `sylabus` a `podminky`). Rozděl na dva soubory
podle toho, jestli má předmět rozvrh v aktuálním semestru (`vyklad_zs`) nebo ne
(`vyklad_ls`) — obojí se načítá dohromady, dělení je jen kvůli velikosti.

- `temata` — sylabus rozsekaný na tematické bloky, jak jdou za sebou. Neshlukuj
  do vlastních kategorií, drž pořadí zdroje.
- `zapocet` — co je potřeba na zápočet. Každá podmínka jedna položka, **s čísly**.
- `zkouska` — jak se počítá známka: váhy, procenta, klasifikační stupnice.
- `pozor` — pasti: penalizace za pozdní odevzdání, „náhradní termíny se nevypisují",
  pravidla o opisování. Prázdné, když tam nic takového není.
- `delka_puvodni` — délka původního textu ve znacích, aby bylo vidět, kolik se zkrátilo.

Když jsou podmínky v SIS prázdné, nech řádek prázdný. **Nedomýšlej je** z toho,
jak to chodí u podobných předmětů.

---

## `anketa_shrnuti.csv` — co anketa říká o konkrétním vyučujícím

`kod,vyucujici,role,uci_v_zs,komentaru,od_data,do_data,plus,minus,souhrn,rozpor`

Zdroj: `data/anketa_komentare.csv`, filtrovaný na dvojici předmět + vyučující + role.
Jeden řádek na **dvojici vyučující + role** (týž člověk může mít zvlášť přednášku
a zvlášť cvičení, hodnocení se liší).

- `komentaru`, `od_data`, `do_data` — kolik připomínek a z jakého rozpětí dat.
  Nikdy neshrnuj bez uvedení, z kolika připomínek to je.
- `plus` / `minus` — konkrétní tvrzení, ne nálepky. „Trpělivě pomáhá i těm, kdo látku
  nezvládají" je použitelné; „dobrý vyučující" není.
- `souhrn` — dvě věty, co si z toho odnést prakticky.
- `rozpor` — **povinný, když se hodnocení v čase mění nebo si připomínky protiřečí.**
  Např. „připomínky z 2024 chválí, dvě z 2026 mluví o recyklovaných materiálech".
  Tohle je nejcennější sloupec celého souboru; průměr přes roky by ten zlom schoval.

Pozor: anketa u garanta ukazuje i připomínky k jiným vyučujícím téhož předmětu,
takže přiřazení může být posunuté. Když si nejsi jistý, komu připomínka patří,
**nepřiřazuj ji** a napiš to do `rozpor`.

---

## `anketa_predmet.csv` — co anketa říká o předmětu samotném

`kod,komentaru,od_data,do_data,prumer,plus,minus,souhrn,varovani`

Totéž, ale nezávisle na tom, pod kým je připomínka vedená: obtížnost, kvalita
materiálů, cvičení, úkoly, bodování, reálnost samostudia. Připomínky s prázdným
sloupcem `vyucujici` (vedené u předmětu jako celku) patří sem.

`varovani` použij, když se **paralelky nebo ročníky popisují neslučitelně** —
tehdy se připomínky nesmějí slučovat do jednoho průměru a je potřeba to říct nahlas.

---

## `stranky.csv` — docházka a reálnost samostudia

`kod,url_kurzu,url_vyucujici,dochazka,dochazka_doklad,nahravky,nahravky_doklad,zapocet,samostudium,poznamka,zdroj`

**Tohle je nejdůležitější a nejnebezpečnější soubor v repu.** Stojí na něm plánování
rozvrhu: kdo se učí sám, potřebuje vědět, které cvičení mu opravdu vynucuje dny
ve škole. Falešné „docházka se neřeší" stojí zápočet.

Zdroj: stránky kurzů a vyučujících (ne SIS — nebo SIS navíc, s uvedením). Textové
výtahy ukládej do `zdroje/stranky/<KOD>-kurz.md`, první dva řádky URL a datum stažení.

`dochazka` — přesně jedna z hodnot, od nejmírnější:

| hodnota | kdy |
|---|---|
| `nerelevantni` | předmět nemá cvičení |
| `neresi_se` | výslovně se nekontroluje |
| `doporucena` | doporučená, ale nekontrolovaná |
| `bodovana` | za účast se sbírají body |
| `povinna` | bez docházky není zápočet |
| `nezjisteno` | nepodařilo se doložit |

**Ke každému tvrzení musí být doslovná citace** v `dochazka_doklad` / `nahravky_doklad`.
Bez citace se píše `nezjisteno`. **Odhad tady není přípustný** — ani „u podobných
předmětů to bývá takhle", ani „z rozsahu 2/2 plyne". Radši deset `nezjisteno`
než jedno vymyšlené `neresi_se`.

`samostudium` — začni slovem `snadne` / `stredni` / `tezke` / `nerealne` a za pomlčkou
větu proč, konkrétně (co přesně se musí odevzdat osobně a v jakém termínu).

---

## `tagy.csv` — oblasti pro filtrování

`kod,tagy`

Slovník slugů je **napevno v `tools/artifact.py`** (konstanta `TAGY`) — používej jen ty,
co tam jsou, jinak se chip nezobrazí. Když je potřeba nová oblast, přidej ji nejdřív
do `TAGY` (slug + český název) a pak teprve do dat.

Cíl je hrubý filtr, ne taxonomie: dva až čtyři tagy na předmět. Tag přiděl podle toho,
co předmět **opravdu učí**, ne podle názvu.

---

## `szz_temata.csv` + `szz_pokryti.csv` — pokrytí státnic

```
szz_temata.csv:   okruh,tema,poradi,formulace_zdroje
szz_pokryti.csv:  okruh,tema,kod,sila,doklad
```

1. Znění požadavků okruhu vezmi z Karolinky (ne z vlastní hlavy) a rozsekej ho
   na **atomická témata** — jedno téma = jedna věc, na kterou se dá dostat otázka.
   `formulace_zdroje` je doslovný úryvek požadavků, ze kterého téma pochází.
2. Pro každé téma najdi předměty, které ho učí. `doklad` je **doslovná citace ze
   sylabu** toho předmětu (`data/anotace.csv`), ne parafráze.
3. `sila` — `hlavni` (předmět tématu věnuje samostatný blok), `castecne`
   (dotkne se ho), nic víc.

**Téma, které nepokrývá žádný předmět, prostě zůstane nepokryté.** Nedoplňuj ho
předmětem, který ho jen ťukne — kontrola pokrytí je tam proto, aby díra byla vidět,
ne aby vycházela. Díru nahlas uživateli s tím, že buď existuje předmět, který jsi
nenašel, nebo si to bude muset nastudovat sám.

---

## Ověřování

Když tyhle soubory píše víc agentů paralelně (což se u větší nabídky vyplatí),
projeď po nich **nezávislou kontrolu**: vezmi vzorek řádků, najdi zdrojová data
a přeměř zejména čísla. Nález agenta neber automaticky — když hlásí chybu s číslem,
ověř i ten **doklad**, ne jen směr tvrzení. A když se ti něco nezdá, ale nemáš
jistotu, radši se zeptej uživatele, než abys „opravil" správný údaj.
