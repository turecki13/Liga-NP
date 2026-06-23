"""
Warstwa dostępu do Google Sheets (gspread + konto serwisowe).

Wymaga w st.secrets:
    [gcp_service_account]   -> zawartość JSON konta serwisowego
    [google_sheets]
    spreadsheet_id = "..."  -> ID arkusza (z URL)
    [admin]
    password = "..."        -> hasło do panelu akceptacji

Gdy sekrety nie są ustawione, skonfigurowane() zwraca False, a aplikacja
pokazuje instrukcję zamiast się wywalać.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import config


def skonfigurowane() -> bool:
    try:
        return (
            "gcp_service_account" in st.secrets
            and "google_sheets" in st.secrets
            and st.secrets["google_sheets"].get("spreadsheet_id")
        )
    except Exception:
        return False


def haslo_admina() -> str | None:
    try:
        return st.secrets["admin"]["password"]
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def _klient():
    import gspread
    from google.oauth2.service_account import Credentials

    zakresy = ["https://www.googleapis.com/auth/spreadsheets"]
    dane = dict(st.secrets["gcp_service_account"])
    poswiadczenia = Credentials.from_service_account_info(dane, scopes=zakresy)
    return gspread.authorize(poswiadczenia)


@st.cache_resource(show_spinner=False)
def _arkusz():
    return _klient().open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])


def _ws(nazwa: str):
    return _arkusz().worksheet(nazwa)


# --- Odczyt (z krótkim cache, żeby nie przekraczać limitów API) --------------
@st.cache_data(ttl=30, show_spinner=False)
def pobierz_mecze() -> list[dict]:
    return _ws(config.WS_MECZE).get_all_records()


@st.cache_data(ttl=30, show_spinner=False)
def pobierz_zgloszenia() -> list[dict]:
    return _ws(config.WS_ZGLOSZENIA).get_all_records()


@st.cache_data(ttl=30, show_spinner=False)
def pobierz_fairplay() -> list[dict]:
    try:
        return _ws(config.WS_FAIRPLAY).get_all_records()
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def pobierz_oceny() -> list[dict]:
    try:
        return _ws(config.WS_FAIRPLAY_OCENY).get_all_records()
    except Exception:
        return []  # zakładka jeszcze nie istnieje – brak ocen


@st.cache_data(ttl=30, show_spinner=False)
def pobierz_ustawienia() -> dict:
    try:
        rows = _ws(config.WS_USTAWIENIA).get_all_records()
        return {str(r.get("Klucz", "")).strip(): str(r.get("Wartosc", "")).strip() for r in rows}
    except Exception:
        return {}


def wyczysc_cache() -> None:
    """Po zapisie czyścimy cache odczytu, żeby od razu widzieć zmiany."""
    pobierz_mecze.clear()
    pobierz_zgloszenia.clear()
    pobierz_fairplay.clear()
    pobierz_oceny.clear()
    pobierz_ustawienia.clear()


def _ws_lub_utworz(nazwa: str, naglowki: list[str]):
    """Zwraca zakładkę; tworzy ją z nagłówkami, jeśli nie istnieje."""
    ar = _arkusz()
    try:
        return ar.worksheet(nazwa)
    except Exception:
        ws = ar.add_worksheet(title=nazwa, rows=200, cols=max(10, len(naglowki)))
        ws.update([naglowki], "A1", value_input_option="RAW")
        return ws


# --- Zapis -------------------------------------------------------------------
def _indeks_kolumny(naglowki: list[str], nazwa: str) -> int:
    """1-based numer kolumny po nazwie nagłówka."""
    return naglowki.index(nazwa) + 1


def _znajdz_wiersz(ws, kolumna_id: str, wartosc: str) -> int | None:
    """Zwraca 1-based numer wiersza, w którym kolumna `kolumna_id` == wartosc."""
    wartosci = ws.get_all_values()
    if not wartosci:
        return None
    naglowki = wartosci[0]
    if kolumna_id not in naglowki:
        return None
    idx = naglowki.index(kolumna_id)
    for nr, wiersz in enumerate(wartosci[1:], start=2):
        if idx < len(wiersz) and str(wiersz[idx]).strip() == str(wartosc).strip():
            return nr
    return None


def dodaj_zgloszenie(z: dict) -> None:
    """Dopisuje nowe zgłoszenie wyniku (status: oczekuje)."""
    ws = _ws(config.WS_ZGLOSZENIA)
    wiersz = [str(z.get(kol, "")) for kol in config.KOL_ZGLOSZENIA]
    # RAW = "6:4" zostaje tekstem, a nie zamienia się na godzinę/czas.
    ws.append_row(wiersz, value_input_option="RAW")
    wyczysc_cache()


def dodaj_ocene(o: dict) -> None:
    """Dopisuje ocenę fair play (informacja dla organizatora)."""
    ws = _ws_lub_utworz(config.WS_FAIRPLAY_OCENY, config.KOL_FAIRPLAY_OCENY)
    wiersz = [str(o.get(kol, "")) for kol in config.KOL_FAIRPLAY_OCENY]
    ws.append_row(wiersz, value_input_option="RAW")
    wyczysc_cache()


def usun_ocene(ocena_id: str) -> None:
    """Usuwa ocenę fair play po jej ID (akcja administratora)."""
    ws = _ws(config.WS_FAIRPLAY_OCENY)
    nr = _znajdz_wiersz(ws, "ID", ocena_id)
    if nr is None:
        raise ValueError("Nie znaleziono oceny do usunięcia.")
    ws.delete_rows(nr)
    wyczysc_cache()


def ustaw_ustawienie(klucz: str, wartosc) -> None:
    """Zapisuje ustawienie (klucz -> wartość) w zakładce 'ustawienia'."""
    ws = _ws_lub_utworz(config.WS_USTAWIENIA, config.KOL_USTAWIENIA)
    nr = _znajdz_wiersz(ws, "Klucz", klucz)
    if nr is not None:
        _aktualizuj(ws, config.KOL_USTAWIENIA, nr, {"Wartosc": str(wartosc)})
    else:
        ws.append_row([str(klucz), str(wartosc)], value_input_option="RAW")
    wyczysc_cache()


def _aktualizuj(ws, naglowki: list[str], nr_wiersza: int, zmiany: dict) -> None:
    import gspread

    komorki = [
        gspread.Cell(nr_wiersza, _indeks_kolumny(naglowki, kol), str(wartosc))
        for kol, wartosc in zmiany.items()
    ]
    ws.update_cells(komorki, value_input_option="RAW")


def akceptuj_zgloszenie(zgloszenie: dict) -> None:
    """Zapisuje wynik do meczu i oznacza zgłoszenie jako zaakceptowane."""
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M")

    ws_m = _ws(config.WS_MECZE)
    nr_m = _znajdz_wiersz(ws_m, "ID", zgloszenie["MeczID"])
    if nr_m is None:
        raise ValueError(f"Nie znaleziono meczu o ID {zgloszenie['MeczID']}.")
    _aktualizuj(ws_m, config.KOL_MECZE, nr_m, {
        "Set1": zgloszenie.get("Set1", ""),
        "Set2": zgloszenie.get("Set2", ""),
        "SuperTB": zgloszenie.get("SuperTB", ""),
        "Wynik": zgloszenie.get("Wynik", ""),
        "Zatwierdzono": teraz,
    })

    ws_z = _ws(config.WS_ZGLOSZENIA)
    nr_z = _znajdz_wiersz(ws_z, "ID", zgloszenie["ID"])
    if nr_z is not None:
        _aktualizuj(ws_z, config.KOL_ZGLOSZENIA, nr_z, {
            "Status": config.STATUS_ZAAKCEPTOWANE, "Rozpatrzono": teraz,
        })
    wyczysc_cache()


def odrzuc_zgloszenie(zgloszenie: dict) -> None:
    teraz = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws_z = _ws(config.WS_ZGLOSZENIA)
    nr_z = _znajdz_wiersz(ws_z, "ID", zgloszenie["ID"])
    if nr_z is None:
        raise ValueError("Nie znaleziono zgłoszenia.")
    _aktualizuj(ws_z, config.KOL_ZGLOSZENIA, nr_z, {
        "Status": config.STATUS_ODRZUCONE, "Rozpatrzono": teraz,
    })
    wyczysc_cache()
