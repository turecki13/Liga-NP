"""
Jednorazowe przygotowanie arkusza Google: tworzy zakładki 'mecze', 'zgloszenia',
'fairplay' z poprawnymi nagłówkami i (opcjonalnie) importuje mecze oraz Fair Play
z plików CSV w folderze ./data.

Użycie (po skonfigurowaniu sekretów w .streamlit/secrets.toml):

    python seed_sheets.py

UWAGA: skrypt NIE nadpisuje istniejących danych w zakładce 'mecze', jeśli ma ona
już więcej niż sam nagłówek.
"""

import csv
from pathlib import Path
from uuid import uuid4

import gspread
from google.oauth2.service_account import Credentials

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

import config

BASE = Path(__file__).parent
DATA = BASE / "data"
SECRETS = BASE / ".streamlit" / "secrets.toml"


def klient_i_arkusz():
    if not SECRETS.exists():
        raise SystemExit("Brak .streamlit/secrets.toml – najpierw skonfiguruj sekrety (patrz README).")
    with open(SECRETS, "rb") as f:
        sek = tomllib.load(f)
    creds = Credentials.from_service_account_info(
        sek["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    return gc.open_by_key(sek["google_sheets"]["spreadsheet_id"])


def zapewnij_zakladke(arkusz, nazwa, naglowki):
    try:
        ws = arkusz.worksheet(nazwa)
    except gspread.WorksheetNotFound:
        ws = arkusz.add_worksheet(title=nazwa, rows=200, cols=max(10, len(naglowki)))
    biezace = ws.row_values(1)
    if biezace != naglowki:
        ws.update([naglowki], "A1", value_input_option="RAW")
    return ws


def czytaj_csv(sciezka):
    if not sciezka.exists():
        return []
    with open(sciezka, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    arkusz = klient_i_arkusz()

    ws_mecze = zapewnij_zakladke(arkusz, config.WS_MECZE, config.KOL_MECZE)
    zapewnij_zakladke(arkusz, config.WS_ZGLOSZENIA, config.KOL_ZGLOSZENIA)
    ws_fp = zapewnij_zakladke(arkusz, config.WS_FAIRPLAY, config.KOL_FAIRPLAY)

    # Import meczów z CSV (tylko gdy zakładka 'mecze' jest pusta).
    if len(ws_mecze.get_all_values()) <= 1:
        wiersze = []
        for klucz, nazwa in config.LIGI.items():
            for m in czytaj_csv(DATA / f"liga_{klucz}_mecze.csv"):
                wiersze.append([
                    uuid4().hex[:8], nazwa, m.get("Kolejka", ""), m.get("Data", ""),
                    m.get("Gospodarz", ""), m.get("Gość", m.get("Gosc", "")),
                    "", "", "", "", "",  # Set1, Set2, SuperTB, Wynik, Zatwierdzono (puste)
                ])
        if wiersze:
            ws_mecze.append_rows(wiersze, value_input_option="RAW")
        print(f"Zaimportowano {len(wiersze)} meczów do zakładki 'mecze'.")
    else:
        print("Zakładka 'mecze' już zawiera dane – pomijam import.")

    # Import Fair Play (tylko gdy pusto).
    if len(ws_fp.get_all_values()) <= 1:
        fp = czytaj_csv(DATA / "fairplay.csv")
        if fp:
            ws_fp.append_rows(
                [[r.get("Zawodnik", ""), r.get("Liga", ""), r.get("Punkty Fair Play", "")] for r in fp],
                value_input_option="RAW",
            )
        print(f"Zaimportowano {len(fp)} wierszy Fair Play.")

    print("Gotowe. Arkusz przygotowany ✔")


if __name__ == "__main__":
    main()
