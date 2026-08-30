#!/usr/bin/env python3
"""Nacte konfiguraci programu z data/program.json.

Jedine misto, kde jsou kreditova minima, SZZ okruhy a doporucene predmety.
Kdyz soubor chybi, skripty spadnou zpatky na sve vlastni defaulty.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CESTA = os.path.join(ROOT, "data", "program.json")


def nacti():
    if not os.path.exists(CESTA):
        return {}
    with open(CESTA, encoding="utf-8") as f:
        return json.load(f)


CFG = nacti()


def minima(default=None):
    return CFG.get("minima") or default or {}


def skupiny(default=None):
    """[(klic, lidsky nazev, minimum), ...] v poradi povinny -> volitelny."""
    nazvy = {"povinny": "povinný", "profilujici": "profilující",
             "rozsirujici": "rozšiřující", "volitelny": "volitelný"}
    m = minima()
    if not m:
        return default or []
    return [(k, nazvy.get(k, k), m[k]) for k in
            ["povinny", "profilujici", "rozsirujici", "volitelny"] if k in m]


def aktivni_okruhy():
    """Kody SZZ okruhu aktivniho zamereni, v poradi ze studijniho planu."""
    z = CFG.get("zamereni", {}).get(CFG.get("zamereni_aktivni", ""), {})
    return list(z.get("okruhy", []))


def szz_nazvy(default=None):
    """{kod okruhu: nazev} — jen okruhy aktivniho zamereni."""
    ok = CFG.get("okruhy", {})
    aktivni = aktivni_okruhy()
    if not aktivni:
        return default or {}
    return {k: ok.get(k, {}).get("nazev", k) for k in aktivni}


def szz_doporucene(default=None):
    ok = CFG.get("okruhy", {})
    aktivni = aktivni_okruhy()
    if not aktivni:
        return default or {}
    return {k: list(ok.get(k, {}).get("doporucene", [])) for k in aktivni}


def semestr(default=("2026", "1")):
    s = CFG.get("semestr") or {}
    return s.get("skr", default[0]), s.get("sem", default[1])


def zamereni_seznam():
    """[(kod, nazev), ...] vsech zamereni v konfiguraci."""
    return [(k, v.get("nazev", k)) for k, v in CFG.get("zamereni", {}).items()]
