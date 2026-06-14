"""
Czysta logika ligi (bez Streamlit i bez Google Sheets) — łatwa do testowania.

Zasady:
- Mecz gramy do 2 wygranych setów.
- Set zwykły: wygrywa 6 przy przewadze min. 2 gemów (6:0…6:4) albo 7:5 / 7:6.
- Przy stanie 1:1 w setach NIE gramy 3. seta, tylko super tie-break do 10
  (przewaga min. 2 punktów, np. 10:7, 11:9).
- Za zwycięstwo w meczu: 2 punkty, za porażkę: 0.
- O miejscu w tabeli decydują: punkty, a przy równości — bilans setów.
"""

from __future__ import annotations

import pandas as pd


class BladWyniku(ValueError):
    """Wyjątek zgłaszany przy niepoprawnym wyniku meczu."""


def parsuj_pare(tekst: str) -> tuple[int, int]:
    """'6:4' / '6-4' / '6 4' -> (6, 4). Rzuca BladWyniku przy złym formacie."""
    if tekst is None:
        raise BladWyniku("Brak wyniku.")
    surowy = str(tekst).strip().replace("-", ":").replace(" ", ":")
    czesci = [c for c in surowy.split(":") if c != ""]
    if len(czesci) != 2:
        raise BladWyniku(f"Niepoprawny format: '{tekst}'. Użyj np. 6:4.")
    try:
        a, b = int(czesci[0]), int(czesci[1])
    except ValueError:
        raise BladWyniku(f"Wynik musi być liczbami: '{tekst}'.")
    if a < 0 or b < 0:
        raise BladWyniku(f"Wynik nie może być ujemny: '{tekst}'.")
    return a, b


def set_poprawny(g: int, o: int) -> bool:
    """Czy (g, o) to poprawny wynik zwykłego seta?"""
    wyzszy, nizszy = max(g, o), min(g, o)
    if g == o:
        return False
    if wyzszy == 6 and 0 <= nizszy <= 4:
        return True
    if wyzszy == 7 and nizszy in (5, 6):
        return True
    return False


def super_tb_poprawny(g: int, o: int) -> bool:
    """Czy (g, o) to poprawny super tie-break (do 10, przewaga min. 2)?"""
    return g != o and max(g, o) >= 10 and abs(g - o) >= 2


def oblicz_mecz(set1: str, set2: str, super_tb: str | None = None) -> dict:
    """
    Liczy wynik meczu z perspektywy GOSPODARZA.

    Zwraca słownik:
        wynik         -> np. '2:0' lub '2:1' (gospodarz:gość)
        sety_g/sety_o -> liczba setów wygranych przez gospodarza / gościa
        gemy_g/gemy_o -> liczba gemów (z dwóch setów; super tie-break się nie liczy)
        zwyciezca     -> 'gospodarz' albo 'gosc'
    Rzuca BladWyniku przy niepoprawnych danych.
    """
    g1, o1 = parsuj_pare(set1)
    g2, o2 = parsuj_pare(set2)
    if not set_poprawny(g1, o1):
        raise BladWyniku(f"Set 1 ({g1}:{o1}) jest niepoprawny. Dozwolone: 6:0–6:4, 7:5, 7:6.")
    if not set_poprawny(g2, o2):
        raise BladWyniku(f"Set 2 ({g2}:{o2}) jest niepoprawny. Dozwolone: 6:0–6:4, 7:5, 7:6.")

    # Gemy liczymy tylko z dwóch rozegranych setów (super tie-break to nie gemy).
    gemy_g, gemy_o = g1 + g2, o1 + o2

    wygral_g_1 = g1 > o1
    wygral_g_2 = g2 > o2

    ma_super_tb = super_tb not in (None, "", " ")

    if wygral_g_1 == wygral_g_2:
        # Ktoś wygrał oba sety — super tie-breaka nie gramy.
        if ma_super_tb:
            raise BladWyniku("Przy wyniku 2:0 nie podaje się super tie-breaka.")
        if wygral_g_1:
            return {"wynik": "2:0", "sety_g": 2, "sety_o": 0,
                    "gemy_g": gemy_g, "gemy_o": gemy_o, "zwyciezca": "gospodarz"}
        return {"wynik": "0:2", "sety_g": 0, "sety_o": 2,
                "gemy_g": gemy_g, "gemy_o": gemy_o, "zwyciezca": "gosc"}

    # Stan 1:1 — wymagany super tie-break.
    if not ma_super_tb:
        raise BladWyniku("Przy stanie 1:1 w setach podaj super tie-break do 10 (np. 10:7).")
    gt, ot = parsuj_pare(super_tb)
    if not super_tb_poprawny(gt, ot):
        raise BladWyniku(f"Super tie-break ({gt}:{ot}) jest niepoprawny. Do 10, przewaga min. 2 (np. 10:7, 11:9).")

    if gt > ot:
        return {"wynik": "2:1", "sety_g": 2, "sety_o": 1,
                "gemy_g": gemy_g, "gemy_o": gemy_o, "zwyciezca": "gospodarz"}
    return {"wynik": "1:2", "sety_g": 1, "sety_o": 2,
            "gemy_g": gemy_g, "gemy_o": gemy_o, "zwyciezca": "gosc"}


def oblicz_tabele(mecze: list[dict]) -> pd.DataFrame:
    """
    Buduje tabelę klasyfikacyjną z listy zatwierdzonych meczów.

    Każdy mecz to słownik z kluczami: Gospodarz, Gość, Set1, Set2, SuperTB.
    Mecze z niepoprawnym/pustym wynikiem są pomijane.

    Punktacja (regulamin): zwycięstwo = 3 pkt, porażka = 1 pkt.
    Kolejność: punkty → bezpośredni pojedynek (gdy remisuje 2) → różnica setów
    → różnica gemów.
    """
    stat: dict[str, dict] = {}
    h2h: dict[tuple[str, str], int] = {}  # (zwycięzca, przegrany) -> liczba zwycięstw

    def gracz(nazwa: str) -> dict:
        return stat.setdefault(
            nazwa,
            {"Zawodnik": nazwa, "Mecze": 0, "Wygrane": 0, "Przegrane": 0,
             "Sety wygrane": 0, "Sety przegrane": 0,
             "Gemy wygrane": 0, "Gemy przegrane": 0, "Punkty": 0},
        )

    for m in mecze:
        gosp = str(m.get("Gospodarz", "")).strip()
        gosc = str(m.get("Gość", "")).strip()
        if not gosp or not gosc:
            continue
        try:
            wynik = oblicz_mecz(m.get("Set1", ""), m.get("Set2", ""), m.get("SuperTB", ""))
        except BladWyniku:
            continue  # mecz bez poprawnego wyniku — pomijamy

        g, o = gracz(gosp), gracz(gosc)
        g["Mecze"] += 1
        o["Mecze"] += 1
        g["Sety wygrane"] += wynik["sety_g"]
        g["Sety przegrane"] += wynik["sety_o"]
        o["Sety wygrane"] += wynik["sety_o"]
        o["Sety przegrane"] += wynik["sety_g"]
        g["Gemy wygrane"] += wynik["gemy_g"]
        g["Gemy przegrane"] += wynik["gemy_o"]
        o["Gemy wygrane"] += wynik["gemy_o"]
        o["Gemy przegrane"] += wynik["gemy_g"]
        if wynik["zwyciezca"] == "gospodarz":
            g["Wygrane"] += 1
            g["Punkty"] += 3
            o["Przegrane"] += 1
            o["Punkty"] += 1
            h2h[(gosp, gosc)] = h2h.get((gosp, gosc), 0) + 1
        else:
            o["Wygrane"] += 1
            o["Punkty"] += 3
            g["Przegrane"] += 1
            g["Punkty"] += 1
            h2h[(gosc, gosp)] = h2h.get((gosc, gosp), 0) + 1

    kolumny = ["Zawodnik", "Mecze", "Wygrane", "Przegrane",
               "Sety wygrane", "Sety przegrane",
               "Gemy wygrane", "Gemy przegrane", "Punkty"]
    if not stat:
        return pd.DataFrame(columns=kolumny)

    # Pomocnicze różnice do rozstrzygania remisów.
    for p in stat.values():
        p["_sety"] = p["Sety wygrane"] - p["Sety przegrane"]
        p["_gemy"] = p["Gemy wygrane"] - p["Gemy przegrane"]

    def klucz_roznic(p):
        return (p["_sety"], p["_gemy"])

    # Grupujemy po punktach i wewnątrz grupy stosujemy regulaminowe tie-breaki.
    gracze = sorted(stat.values(), key=lambda p: p["Punkty"], reverse=True)
    uporzadkowani: list[dict] = []
    i = 0
    while i < len(gracze):
        j = i
        while j < len(gracze) and gracze[j]["Punkty"] == gracze[i]["Punkty"]:
            j += 1
        grupa = gracze[i:j]
        if len(grupa) == 2:
            a, b = grupa
            wa = h2h.get((a["Zawodnik"], b["Zawodnik"]), 0)
            wb = h2h.get((b["Zawodnik"], a["Zawodnik"]), 0)
            if wa != wb:
                grupa = [a, b] if wa > wb else [b, a]
            else:
                grupa = sorted(grupa, key=klucz_roznic, reverse=True)
        else:
            grupa = sorted(grupa, key=klucz_roznic, reverse=True)
        uporzadkowani.extend(grupa)
        i = j

    df = pd.DataFrame(uporzadkowani).reset_index(drop=True)
    return df[kolumny]
