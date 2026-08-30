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

### Jak najít stránku kurzu

SIS na stránku kurzu **většinou neodkazuje**, takže je to detektivní práce. Čtyři
zdroje v tomhle pořadí, končíš první, která zabere:

1. **Anotace v `data/anotace.csv`.** Vyučující tam URL často zmíní. Vytáhni je
   hromadně a máš třetinu práce hotovou zadarmo:
   ```bash
   python3 -c "
   import csv, re
   for r in csv.DictReader(open('data/anotace.csv', encoding='utf-8')):
       u = re.findall(r'https?://[^\s,;)\"]+',
                      ' '.join([r['anotace'], r['sylabus'], r['podminky']]))
       u = [x for x in u if 'is.cuni.cz' not in x and 'w3.org' not in x]
       if u: print(r['kod'], ' '.join(dict.fromkeys(u))[:200])"
   ```
2. **Domovská stránka vyučujícího.** Jméno je v `data/sis.csv` (`vyucujici`, `garant`),
   pracoviště taky. Stránky bývají na katedrálních doménách ve tvaru
   `<katedra>.mff.cuni.cz/~<prijmeni>/`:
   `ktiml.mff.cuni.cz` (KTIML), `ufal.mff.cuni.cz` (ÚFAL, kurzy pod
   `/courses/<kod malymi>`), `ksvi.mff.cuni.cz`, `ksi.mff.cuni.cz` (KSI),
   `cgg.mff.cuni.cz` (počítačová grafika), `karlin.mff.cuni.cz` (KPMS, matematika).
   Kurz pak bývá v podadresáři (`~mraz/nn/`). Někteří lidé mají web mimo fakultu.
3. **Vyhledávání.** `WebSearch` na `"<KÓD> <název předmětu> MFF"` — kód předmětu je
   dost unikátní, aby to trefilo.
4. **Moodle `dl1.cuni.cz` / `dl2.cuni.cz`.** Odkaz najdeš, obsah ne — je za
   přihlášením. To je legitimní zjištění: napiš do `poznamka`, že materiály jsou
   jen v Moodlu za CAS, a nech `nezjisteno`.

Když nenajdeš nic, řádek **stejně založ** — s `nezjisteno` a poznámkou, kde jsi
hledal. Chybějící řádek vypadá jako „ještě jsme se k tomu nedostali"; řádek
s `nezjisteno` je informace, že to zjistit nešlo.

### Na co se na té stránce dívat

Ne na celý obsah kurzu, ale na čtyři věci:

- **sekce o zápočtu a hodnocení** — tam bývá věta o docházce a bodech za účast,
- **rozpis přednášek** — jestli u nich jsou slajdy nebo videa,
- **datum poslední aktualizace** — stará stránka může popisovat jiná pravidla než
  aktuální SIS. Když si odporují, uveď obojí a napiš, co je novější.
- **termíny, které se nedají dohnat** — prezentace projektu, testy psané na cvičení,
  konzultace v půlce semestru. Tohle je přesně to, co rozhoduje o samostudiu.

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

### Kdy vůbec pouštět agenty

Fan-out není zadarmo: každý agent startuje bez kontextu a musí si ho odvodit znovu,
takže se platí za to, co ty už víš. Rozhoduj podle objemu, ne ze zvyku:

| Situace | Co udělat |
|---|---|
| pár předmětů (do zhruba deseti) | **udělej to sám**, fan-out se nevyplatí |
| celý program nebo zaměření (desítky předmětů) | rozděl mezi agenty |
| jednorázová oprava, doplnění jednoho řádku | sám |
| `stranky.csv` pro víc než deset předmětů | agenti, je to nejpomalejší část |

Ptej se sám sebe, jestli je práce **opravdu paralelní**. Sylaby a ankety ano —
předměty na sobě nezávisí. Pokrytí státnic (`szz_*`) spíš ne: potřebuje přehled
přes celou nabídku najednou, rozsekané po dávkách vyjde hůř, než když to uděláš vcelku.

A ber ohled na to, že uživatel platí. Když si nejsi jistý, jestli se rozsah vyplatí,
**řekni mu, kolik toho je, a nech ho rozhodnout** — třeba mu stačí jádro plánu
a zbytek nechá na později.

### Kterým modelem

- **`stranky.csv`** — nejsilnějším, co máš (Opus). Je to jediný soubor, kde se
  rozhoduje z neúplných a protiřečících si zdrojů a kde chyba stojí zápočet.
  Sem slabší model nedávej.
- **`szz_temata.csv` / `szz_pokryti.csv`** — taky Opus. Rozhodnout, jestli sylabus
  opravdu pokrývá téma státnice, je úsudek, ne přepis.
- **`vyklad_*.csv`, `anketa_shrnuti.csv`, `anketa_predmet.csv`** — středním modelem
  (Sonnet). Je to práce se zdrojem, který už máš stažený; hlavní riziko jsou čísla,
  a to ošetří kontrola po dávce, ne velikost modelu.
- **`tagy.csv`** — klidně nejlevnějším. Přiřadit dva až čtyři tagy ze zavřeného
  slovníku je mechanické.

### Jak rozvrhnout práci mezi agenty

U větší nabídky se to bez paralelizace protáhne. Rozděl to takhle:

- **Najednou nech běžet zhruba tři až pět agentů.** Víc se hůř kontroluje a stejně
  to nezrychlí — úzké hrdlo je stahování stránek, ne tvoje čekání.

- **Jeden agent = jedna dávka předmětů (zhruba osm) a jeden cílový soubor.**
  Nedávej jednomu agentovi „všechno o pěti předmětech" — formáty se pletou.
- Agentovi předej **konkrétní kódy**, cestu k výstupnímu souboru, hlavičku CSV
  a odkaz na příslušnou sekci tohohle dokumentu. Ať zapisuje do vlastního
  dočasného souboru a ty ho sloučíš — souběžný zápis do jednoho CSV je ztráta dat.
- `stranky.csv` potřebuje web, takže je nejpomalejší; pusť ji jako první a ostatní
  souběžně vedle.
- Po každé dávce si **sám otevři dva tři zdroje** a ověř, co agent napsal.

Po dokončení projeď **nezávislou kontrolu**: vezmi vzorek řádků, najdi zdrojová data
a přeměř zejména čísla. Nález agenta neber automaticky — když hlásí chybu s číslem,
ověř i ten **doklad**, ne jen směr tvrzení. A když se ti něco nezdá, ale nemáš
jistotu, radši se zeptej uživatele, než abys „opravil" správný údaj.
