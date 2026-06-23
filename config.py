"""Wspólna konfiguracja: lista lig (bez emoji) używana w całej aplikacji."""

# Kolejność = kolejność w menu. Klucz techniczny -> czytelna nazwa ligi.
LIGI: dict[str, str] = {
    "k1": "Liga 1 kobiet",
    "k2": "Liga 2 kobiet",
    "k3": "Liga 3 kobiet",
    "m1": "Liga 1 mężczyzn",
    "m2": "Liga 2 mężczyzn",
    "m3": "Liga 3 mężczyzn",
}

# Nazwy zakładek (worksheetów) w arkuszu Google.
WS_MECZE = "mecze"
WS_ZGLOSZENIA = "zgloszenia"
WS_FAIRPLAY = "fairplay"
WS_FAIRPLAY_OCENY = "fairplay_oceny"
WS_USTAWIENIA = "ustawienia"

# Nagłówki kolumn w poszczególnych zakładkach arkusza.
KOL_MECZE = [
    "ID", "Liga", "Kolejka", "Data",
    "Gospodarz", "Gość", "Set1", "Set2", "SuperTB", "Wynik", "Zatwierdzono",
]
KOL_ZGLOSZENIA = [
    "ID", "Czas", "MeczID", "Liga", "Kolejka", "Gospodarz", "Gość",
    "Set1", "Set2", "SuperTB", "Wynik", "Status", "Rozpatrzono",
]
KOL_FAIRPLAY = ["Zawodnik", "Liga", "Punkty Fair Play"]
KOL_FAIRPLAY_OCENY = [
    "ID", "Czas", "MeczID", "Liga", "Kolejka",
    "Oceniający", "Oceniany", "Ocena", "Komentarz",
]
KOL_USTAWIENIA = ["Klucz", "Wartosc"]

# Klucz ustawienia: do której kolejki włącznie pokazujemy zaległe mecze.
KLUCZ_ZALEGLE_DO_KOLEJKI = "zalegle_do_kolejki"

# Statusy zgłoszeń
STATUS_OCZEKUJE = "oczekuje"
STATUS_ZAAKCEPTOWANE = "zaakceptowane"
STATUS_ODRZUCONE = "odrzucone"
