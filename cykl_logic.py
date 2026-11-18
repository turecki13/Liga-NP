"""
Czysta logika cyklu turniejów (bez Streamlit i bez Google Sheets).

Model:
- Mecz rozstrzygany czasem; wynik to liczba gemów (np. 6:2, 11:0).
  Zwycięzca = więcej gemów. Mecz „do zera" = przeciwnik 0 gemów.
- Grupa: 4 zawodników, każdy z każdym (6 meczów).
- Kolejność w grupie:
    1) liczba wygranych meczów,
    2) różnica gemów (zdobyte − stracone),
    3) bezpośredni pojedynek (mini-tabela wśród remisujących).
- Punkty do klasyfikacji generalnej za miejsce w grupie: 30 / 20 / 15 / 10
  (naliczane, gdy grupa jest kompletna — wszystkie mecze rozegrane).
- Bonus +2 do generalnej za każdy mecz wygrany „do zera" (liczony od razu).
"""

from __future__ import annotations

from itertools import combinations

import pandas as pd

import cykl_config as C


# --- Pojedynczy mecz ----------------------------------------------------------
def wynik_gemowy(mecz: dict) -> tuple[int, int] | None:
    """(GemyA, GemyB) jako liczby, albo None gdy brak kompletnego wyniku."""
    a, b = mecz.get("GemyA", ""), mecz.get("GemyB", "")
    if a is None or b is None or str(a).strip() == "" or str(b).strip() == "":
        return None
    try:
        ga, gb = int(float(a)), int(float(b))
    except (TypeError, ValueError):
        return None
    if ga < 0 or gb < 0 or ga == gb:
        return None  # remis gemowy jest niemożliwy wg regulaminu (zawsze jest zwycięzca)
    return ga, gb


def pary_grupy(zawodnicy: list[str]) -> list[tuple[str, str]]:
    """Wszystkie pary (mecze każdy z każdym) dla listy zawodników."""
    return list(combinations(zawodnicy, 2))


def _pusta_statystyka(nazwa: str) -> dict:
    return {
        "Zawodnik": nazwa, "Mecze": 0, "Wygrane": 0, "Przegrane": 0,
        "Gemy zdobyte": 0, "Gemy stracone": 0, "Bonusy": 0,
    }


def standings_grupy(zawodnicy: list[str], mecze: list[dict]) -> list[dict]:
    """
    Zwraca uporządkowaną listę statystyk zawodników grupy (od 1. miejsca).
    Każdy wpis zawiera też 'Różnica gemów', 'Miejsce' (gdy grupa kompletna) i
    'Punkty' (punkty do generalnej za miejsce — tylko gdy grupa kompletna).
    """
    zawodnicy = [z for z in zawodnicy if str(z).strip()]
    stat = {z: _pusta_statystyka(z) for z in zawodnicy}
    rozegrane: list[tuple[str, str, int, int]] = []  # (a, b, gemyA, gemyB)

    for m in mecze:
        res = wynik_gemowy(m)
        if res is None:
            continue
        a, b = str(m.get("ZawodnikA", "")).strip(), str(m.get("ZawodnikB", "")).strip()
        if a not in stat or b not in stat:
            continue
        ga, gb = res
        stat[a]["Mecze"] += 1
        stat[b]["Mecze"] += 1
        stat[a]["Gemy zdobyte"] += ga
        stat[a]["Gemy stracone"] += gb
        stat[b]["Gemy zdobyte"] += gb
        stat[b]["Gemy stracone"] += ga
        if ga > gb:
            stat[a]["Wygrane"] += 1
            stat[b]["Przegrane"] += 1
            if gb == 0:
                stat[a]["Bonusy"] += C.BONUS_DO_ZERA
        else:
            stat[b]["Wygrane"] += 1
            stat[a]["Przegrane"] += 1
            if ga == 0:
                stat[b]["Bonusy"] += C.BONUS_DO_ZERA
        rozegrane.append((a, b, ga, gb))

    for z in stat.values():
        z["Różnica gemów"] = z["Gemy zdobyte"] - z["Gemy stracone"]

    kolejnosc = _uporzadkuj(zawodnicy, stat, rozegrane)

    # Grupa kompletna = rozegrano wszystkie pary.
    komplet = len(rozegrane) >= len(pary_grupy(zawodnicy)) and len(zawodnicy) >= 2
    wynik = []
    for i, naz in enumerate(kolejnosc, start=1):
        wpis = dict(stat[naz])
        if komplet:
            wpis["Miejsce"] = i
            wpis["Punkty"] = C.PUNKTY_ZA_MIEJSCE.get(i, 0)
        else:
            wpis["Miejsce"] = None
            wpis["Punkty"] = 0
        wynik.append(wpis)
    return wynik


def _uporzadkuj(zawodnicy: list[str], stat: dict,
                rozegrane: list[tuple[str, str, int, int]]) -> list[str]:
    """Sortuje nazwiska: wygrane → różnica gemów → bezpośredni pojedynek → nazwisko."""

    def klucz_globalny(z: str) -> tuple:
        return (stat[z]["Wygrane"], stat[z]["Różnica gemów"])

    # Malejąco po (wygrane, różnica gemów); remisy rozbijamy niżej mini-tabelą h2h.
    wstepna = sorted(zawodnicy, key=klucz_globalny, reverse=True)

    # Grupujemy po równym (wygrane, różnica) i wewnątrz stosujemy mini-tabelę h2h.
    wynik: list[str] = []
    i = 0
    while i < len(wstepna):
        j = i
        while (j < len(wstepna)
               and klucz_globalny(wstepna[j]) == klucz_globalny(wstepna[i])):
            j += 1
        remisujacy = wstepna[i:j]
        if len(remisujacy) > 1:
            remisujacy = _rozstrzygnij_h2h(remisujacy, rozegrane)
        wynik.extend(remisujacy)
        i = j
    return wynik


def _rozstrzygnij_h2h(osoby: list[str],
                      rozegrane: list[tuple[str, str, int, int]]) -> list[str]:
    """Mini-tabela wśród remisujących: wygrane między sobą → różnica gemów → nazwisko."""
    podzbior = set(osoby)
    wyg = {z: 0 for z in osoby}
    gd = {z: 0 for z in osoby}
    for a, b, ga, gb in rozegrane:
        if a in podzbior and b in podzbior:
            gd[a] += ga - gb
            gd[b] += gb - ga
            if ga > gb:
                wyg[a] += 1
            else:
                wyg[b] += 1
    # Malejąco po wygranych między sobą i różnicy gemów między sobą; na końcu nazwisko.
    return sorted(osoby, key=lambda z: (-wyg[z], -gd[z], z.lower()))


# --- Klasyfikacja generalna ---------------------------------------------------
def klasyfikacja_generalna(grupy: list[dict], mecze: list[dict],
                           plec: str) -> pd.DataFrame:
    """
    Buduje klasyfikację generalną danej płci na podstawie wszystkich turniejów.

    grupy: wiersze {TurniejID, Plec, Grupa, Zawodnik}.
    mecze: wiersze {TurniejID, Plec, Grupa, ZawodnikA, ZawodnikB, GemyA, GemyB, ...}.

    Zwraca DataFrame posortowany malejąco po 'Punkty' z kolumnami:
    Zawodnik, Pkt za miejsca, Bonusy, Punkty, Turnieje (liczba turniejów z udziałem).
    """
    grupy = [g for g in grupy if str(g.get("Plec", "")).strip() == plec]
    mecze = [m for m in mecze if str(m.get("Plec", "")).strip() == plec]

    # Roster: wszyscy zawodnicy tej płci, którzy są w jakiejkolwiek grupie.
    pkt_miejsca: dict[str, int] = {}
    bonusy: dict[str, int] = {}
    turnieje_udzial: dict[str, set] = {}

    for g in grupy:
        naz = str(g.get("Zawodnik", "")).strip()
        if naz:
            pkt_miejsca.setdefault(naz, 0)
            bonusy.setdefault(naz, 0)
            turnieje_udzial.setdefault(naz, set()).add(str(g.get("TurniejID", "")).strip())

    # Składy grup: (TurniejID, Grupa) -> lista zawodników.
    sklady: dict[tuple[str, str], list[str]] = {}
    for g in grupy:
        klucz = (str(g.get("TurniejID", "")).strip(), str(g.get("Grupa", "")).strip())
        naz = str(g.get("Zawodnik", "")).strip()
        if naz:
            sklady.setdefault(klucz, []).append(naz)

    # Mecze pogrupowane po (TurniejID, Grupa).
    mecze_grupy: dict[tuple[str, str], list[dict]] = {}
    for m in mecze:
        klucz = (str(m.get("TurniejID", "")).strip(), str(m.get("Grupa", "")).strip())
        mecze_grupy.setdefault(klucz, []).append(m)

    # Punkty za miejsca (tylko kompletne grupy) + bonusy.
    for klucz, zawodnicy in sklady.items():
        tabela = standings_grupy(zawodnicy, mecze_grupy.get(klucz, []))
        for wpis in tabela:
            naz = wpis["Zawodnik"]
            pkt_miejsca[naz] = pkt_miejsca.get(naz, 0) + int(wpis.get("Punkty", 0))
            bonusy[naz] = bonusy.get(naz, 0) + int(wpis.get("Bonusy", 0))

    wiersze = []
    for naz in pkt_miejsca:
        pm = pkt_miejsca.get(naz, 0)
        bo = bonusy.get(naz, 0)
        wiersze.append({
            "Zawodnik": naz,
            "Pkt za miejsca": pm,
            "Bonusy": bo,
            "Punkty": pm + bo,
            "Turnieje": len(turnieje_udzial.get(naz, set())),
        })

    kolumny = ["Zawodnik", "Pkt za miejsca", "Bonusy", "Punkty", "Turnieje"]
    if not wiersze:
        return pd.DataFrame(columns=kolumny)

    df = pd.DataFrame(wiersze)
    df = df.sort_values(["Punkty", "Pkt za miejsca", "Zawodnik"],
                        ascending=[False, False, True]).reset_index(drop=True)
    return df[kolumny]


def generuj_mecze_grupy(turniej_id: str, plec: str, grupa: str,
                        zawodnicy: list[str]) -> list[dict]:
    """Tworzy wiersze meczów (każdy z każdym) dla grupy — bez wyników/kortów."""
    zawodnicy = [z for z in zawodnicy if str(z).strip()]
    mecze = []
    for i, (a, b) in enumerate(pary_grupy(zawodnicy), start=1):
        mecze.append({
            "ID": f"{turniej_id}-{plec}-{grupa}-{i}",
            "TurniejID": turniej_id, "Plec": plec, "Grupa": grupa,
            "ZawodnikA": a, "ZawodnikB": b,
            "Kort": "", "Godzina": "", "GemyA": "", "GemyB": "",
        })
    return mecze
