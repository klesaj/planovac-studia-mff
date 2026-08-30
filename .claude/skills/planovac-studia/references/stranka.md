# Stránka: generování, testování, publikace

`tools/artifact.py` z CSV v `data/` vyrobí jednu samostatnou HTML stránku
`artifact/plan.html` (všechna data jsou zapečená dovnitř, nic se nestahuje za běhu).
Publikuje se jako Artifact.

```bash
python3 tools/artifact.py
```

Pak stránku publikuj nástrojem Artifact z cesty `artifact/plan.html`.
**Při každé další publikaci předej stejnou cestu** (a v nové konverzaci i `url`
existujícího artifactu), ať zůstane stejný odkaz.

## Co stránka umí

Tři vrstvy, každá s vlastním klíčem v `localStorage`, dají se mít zapnuté naráz:

1. **Přehled** — týdenní rozvrhová mřížka a dlaždice předmětů po skupinách.
   Nad nimi filtr: hledání, „jen zimní semestr", „jen doporučené plánem",
   chipy **zaměření** (`data/predmety.csv` → `zamereni`; předmět označený `vse`
   je společný celému programu a filtrem nezmizí) a chipy **oblastí**
   (`data/tagy.csv`; víc zapnutých = sjednocení, ne průnik).
2. **Plánovací režim** — klikáním na dlaždice vzniká plán. Počítá kredity po
   skupinách proti minimům z `data/program.json`, pokrytí státnicových okruhů
   po tématech, rozvržení do šesti semestrů, průběžné kontroly a kolize přednášek.
   Panel „Vzít výběr do repozitáře" vypíše `kod,plan_semestr` k zapsání do CSV.
3. **Režim stavby rozvrhu** — klikáním na bloky v mřížce vzniká konkrétní rozvrh.
   Počítá kredity, hodiny, **počet dní ve škole**, kolize, chybějící cvičení,
   docházkové riziko z `data/stranky.csv` a rozdíly proti plánovacímu výběru.

Detail každého předmětu je pod kotvou `#p-<KOD>`, takže na něj jde odkázat.

Tlačítka **„Načíst plán z repozitáře"** a **„Načíst doporučený rozvrh"** vezmou
`plan_semestr` z `data/predmety.csv` a paralelky z `data/rozvrh_vyber.csv` —
uživatel nic nekopíruje. Data se do stránky zapékají při generování, takže po
**každé** změně CSV je nutné `tools/artifact.py` a znovu publikovat.

## Sandbox: žádné nativní dialogy

`confirm()`, `prompt()` i `alert()` jsou v publikovaném artifactu umlčené —
`confirm` vrátí `false`, `prompt` vrátí `null` a nic se nestane. Proto se
destruktivní akce potvrzuje **dvojklikem na tlačítko** (funkce `potvrd()`)
a hlásí do proužku `.lista-hlaska`. **Nikdy sem nevracej nativní dialogy.**

## Než něco změníš v artifact.py: projeď stránku v jsdom

`node --check` nestačí — projde i stránka, do jejíž šablony se zapomněl vložit
celý JS blok. Postup:

```bash
mkdir -p /tmp/jsdomtest && cd /tmp/jsdomtest && npm i jsdom
```

```js
// test.mjs
import { JSDOM } from 'jsdom';
import fs from 'fs';
const html = fs.readFileSync('artifact/plan.html','utf8');
const chyby = [];
const vc = new (await import('jsdom')).VirtualConsole()
  .on('jsdomError', e => chyby.push('jsdomError: ' + e.message));
const { window } = new JSDOM(html, { runScripts:'dangerously', pretendToBeVisual:true,
                                     virtualConsole: vc });
const d = window.document;
await new Promise(r => setTimeout(r, 300));
const videt = () => Array.from(d.querySelectorAll('.dlazdice')).filter(x => !x.hidden).length;
console.log('dlaždic:', d.querySelectorAll('.dlazdice').length, 'vidět:', videt());
// proklikej chipy, přepínače režimů a všechna tlačítka
for (const b of d.querySelectorAll('.zam-tlac, .tag-tlac, button')) {
  b.dispatchEvent(new window.Event('click', { bubbles:true }));
}
window.location.hash = '#p-' + d.querySelector('.dlazdice').dataset.kod;
window.dispatchEvent(new window.Event('hashchange'));
console.log(chyby.length ? chyby.join('\n') : 'bez chyb');
```

`Not implemented: Window's scrollTo()` je omezení jsdomu, ne chyba stránky —
tenhle jeden hlas ignoruj. Cokoli jiného je regrese.

## Design stránky

Stránka je česky, věcně, bez marketingového tónu. Barvy skupin předmětů
(`--povinny`, `--profilujici`, `--rozsirujici`, `--volitelny`) jsou definované
pro světlé i tmavé téma; **každou novou barvu definuj v obou**, jinak se
v jednom z nich ztratí. Data se nesmí zobrazovat jako jistota, když jistá nejsou:
předběžný rozvrh, chybějící lístek nebo nezjištěná docházka se píšou jako takové.
