"""
Warstwa danych cyklu turniejów.

Dwa backendy za tym samym interfejsem:
  • Google Sheets — gdy w st.secrets jest [cykl_google_sheets].spreadsheet_id
    oraz [gcp_service_account] (to samo konto serwisowe co liga).
  • Lokalny JSON (data/cykl/*.json) — gdy arkusz nie jest skonfigurowany;
    pełny odczyt i zapis, żeby appkę dało się uruchomić i testować bez arkusza.

Dane są małe (kilka turniejów × grupy × mecze), więc zapis przepisuje całą
zakładkę/plik — prosto i bez błędów indeksowania wierszy.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import cykl_config as C
import cykl_logic

BASE_DIR = Path(__file__).parent
LOCAL_DIR = BASE_DIR / "data" / "cykl"

_RODZAJE = {
    C.WS_GRUPY: C.KOL_GRUPY,
    C.WS_MECZE: C.KOL_MECZE,
}


# --- Tryb / konfiguracja ------------------------------------------------------
def skonfigurowany_arkusz() -> bool:
    try:
        return (
            C.SEKRET_KONTO in st.secrets
            and C.SEKRET_ARKUSZ in st.secrets
            and bool(st.secrets[C.SEKRET_ARKUSZ].get("spreadsheet_id"))
        )
    except Exception:
        return False


def haslo_admina() -> str | None:
    try:
        return st.secrets[C.SEKRET_ADMIN]["password"]
    except Exception:
        return None


def tryb() -> str:
    return "Google Sheets" if skonfigurowany_arkusz() else "lokalny (JSON)"


# --- Backend: Google Sheets ---------------------------------------------------
@st.cache_resource(show_spinner=False)
def _klient():
    import gspread
    from google.oauth2.service_account import Credentials

    zakresy = ["https://www.googleapis.com/auth/spreadsheets"]
    dane = dict(st.secrets[C.SEKRET_KONTO])
    pos = Credentials.from_service_account_info(dane, scopes=zakresy)
    return gspread.authorize(pos)


@st.cache_resource(show_spinner=False)
def _arkusz():
    return _klient().open_by_key(st.secrets[C.SEKRET_ARKUSZ]["spreadsheet_id"])


def _ws(rodzaj: str):
    ar = _arkusz()
    naglowki = _RODZAJE[rodzaj]
    try:
        return ar.worksheet(rodzaj)
    except Exception:
        ws = ar.add_worksheet(title=rodzaj, rows=400, cols=max(10, len(naglowki)))
        ws.update([naglowki], "A1", value_input_option="RAW")
        return ws


def _sheets_wczytaj(rodzaj: str) -> list[dict]:
    return _ws(rodzaj).get_all_records()


def _sheets_zapisz(rodzaj: str, wiersze: list[dict]) -> None:
    ws = _ws(rodzaj)
    naglowki = _RODZAJE[rodzaj]
    dane = [naglowki] + [[str(w.get(k, "")) for k in naglowki] for w in wiersze]
    ws.clear()
    ws.update(dane, "A1", value_input_option="RAW")


# --- Backend: lokalny JSON ----------------------------------------------------
def _plik(rodzaj: str) -> Path:
    return LOCAL_DIR / f"{rodzaj}.json"


def _local_wczytaj(rodzaj: str) -> list[dict]:
    p = _plik(rodzaj)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _local_zapisz(rodzaj: str, wiersze: list[dict]) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    naglowki = _RODZAJE[rodzaj]
    znorm = [{k: w.get(k, "") for k in naglowki} for w in wiersze]
    _plik(rodzaj).write_text(json.dumps(znorm, ensure_ascii=False, indent=2),
                             encoding="utf-8")


# --- Wspólny odczyt/zapis -----------------------------------------------------
@st.cache_data(ttl=20, show_spinner=False)
def _wczytaj(rodzaj: str) -> list[dict]:
    if skonfigurowany_arkusz():
        return _sheets_wczytaj(rodzaj)
    return _local_wczytaj(rodzaj)


def _zapisz(rodzaj: str, wiersze: list[dict]) -> None:
    if skonfigurowany_arkusz():
        _sheets_zapisz(rodzaj, wiersze)
    else:
        _local_zapisz(rodzaj, wiersze)
    _wczytaj.clear()


# --- API wysokiego poziomu ----------------------------------------------------
def pobierz_grupy() -> list[dict]:
    return _wczytaj(C.WS_GRUPY)


def pobierz_mecze() -> list[dict]:
    return _wczytaj(C.WS_MECZE)


def _para_klucz(a: str, b: str) -> frozenset:
    return frozenset({str(a).strip(), str(b).strip()})


def zapisz_grupe(turniej_id: str, plec: str, grupa: str,
                 zawodnicy: list[str]) -> None:
    """
    Ustawia skład grupy (lista zawodników) i regeneruje mecze każdy-z-każdym,
    zachowując korty/godziny/wyniki dla par, które pozostały w składzie.
    """
    grupa = str(grupa).strip()
    zawodnicy = [str(z).strip() for z in zawodnicy if str(z).strip()]

    # --- grupy: podmień wiersze tej (turniej, plec, grupa) ---
    grupy = pobierz_grupy()
    grupy = [g for g in grupy if not (
        str(g.get("TurniejID", "")).strip() == turniej_id
        and str(g.get("Plec", "")).strip() == plec
        and str(g.get("Grupa", "")).strip() == grupa
    )]
    for z in zawodnicy:
        grupy.append({"TurniejID": turniej_id, "Plec": plec, "Grupa": grupa, "Zawodnik": z})
    _zapisz(C.WS_GRUPY, grupy)

    # --- mecze: zachowaj dane istniejących par, zregeneruj komplet ---
    mecze = pobierz_mecze()
    stare_tej_grupy = {
        _para_klucz(m.get("ZawodnikA", ""), m.get("ZawodnikB", "")): m
        for m in mecze
        if str(m.get("TurniejID", "")).strip() == turniej_id
        and str(m.get("Plec", "")).strip() == plec
        and str(m.get("Grupa", "")).strip() == grupa
    }
    inne = [m for m in mecze if not (
        str(m.get("TurniejID", "")).strip() == turniej_id
        and str(m.get("Plec", "")).strip() == plec
        and str(m.get("Grupa", "")).strip() == grupa
    )]

    nowe = cykl_logic.generuj_mecze_grupy(turniej_id, plec, grupa, zawodnicy)
    for m in nowe:
        stara = stare_tej_grupy.get(_para_klucz(m["ZawodnikA"], m["ZawodnikB"]))
        if stara:
            for pole in ("Kort", "Godzina", "GemyA", "GemyB"):
                m[pole] = stara.get(pole, "")
    _zapisz(C.WS_MECZE, inne + nowe)


def usun_grupe(turniej_id: str, plec: str, grupa: str) -> None:
    grupa = str(grupa).strip()

    def nie_ta(w):
        return not (
            str(w.get("TurniejID", "")).strip() == turniej_id
            and str(w.get("Plec", "")).strip() == plec
            and str(w.get("Grupa", "")).strip() == grupa
        )

    _zapisz(C.WS_GRUPY, [g for g in pobierz_grupy() if nie_ta(g)])
    _zapisz(C.WS_MECZE, [m for m in pobierz_mecze() if nie_ta(m)])


def aktualizuj_mecz(mecz_id: str, zmiany: dict) -> None:
    """Zmienia pola meczu (Kort / Godzina / GemyA / GemyB) po jego ID."""
    mecze = pobierz_mecze()
    trafiony = False
    for m in mecze:
        if str(m.get("ID", "")).strip() == str(mecz_id).strip():
            for k, v in zmiany.items():
                if k in C.KOL_MECZE:
                    m[k] = v
            trafiony = True
            break
    if not trafiony:
        raise ValueError(f"Nie znaleziono meczu o ID {mecz_id}.")
    _zapisz(C.WS_MECZE, mecze)


def nazwy_grup(turniej_id: str, plec: str) -> list[str]:
    nazwy = {
        str(g.get("Grupa", "")).strip()
        for g in pobierz_grupy()
        if str(g.get("TurniejID", "")).strip() == turniej_id
        and str(g.get("Plec", "")).strip() == plec
        and str(g.get("Grupa", "")).strip()
    }
    return sorted(nazwy)


def zawodnicy_grupy(turniej_id: str, plec: str, grupa: str) -> list[str]:
    return [
        str(g.get("Zawodnik", "")).strip()
        for g in pobierz_grupy()
        if str(g.get("TurniejID", "")).strip() == turniej_id
        and str(g.get("Plec", "")).strip() == plec
        and str(g.get("Grupa", "")).strip() == str(grupa).strip()
        and str(g.get("Zawodnik", "")).strip()
    ]


def mecze_grupy(turniej_id: str, plec: str, grupa: str) -> list[dict]:
    return [
        m for m in pobierz_mecze()
        if str(m.get("TurniejID", "")).strip() == turniej_id
        and str(m.get("Plec", "")).strip() == plec
        and str(m.get("Grupa", "")).strip() == str(grupa).strip()
    ]
