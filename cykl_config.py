"""
Konfiguracja aplikacji „Cykl Turniejów Singlowych NP Tennis Academy".

Niezależna od Letniej Ligi (app.py / config.py). Trzyma stałe cyklu:
listę turniejów, podział na płcie, nazwy zakładek arkusza / plików danych,
punktację do klasyfikacji generalnej i próg kwalifikacji do Masters.
"""

from __future__ import annotations

# --- Turnieje cyklu -----------------------------------------------------------
# id  – klucz techniczny (stabilny, używany w danych),
# nazwa – etykieta w zakładce, data – dzień turnieju, masters – finał?
TURNIEJE: list[dict] = [
    {"id": "t1", "nazwa": "Turniej 1", "data": "22.11.2026", "masters": False},
    {"id": "t2", "nazwa": "Turniej 2", "data": "19.12.2026", "masters": False},
    {"id": "t3", "nazwa": "Turniej 3", "data": "06.01.2027", "masters": False},
    {"id": "t4", "nazwa": "Turniej 4", "data": "07.02.2027", "masters": False},
    {"id": "t5", "nazwa": "Turniej 5", "data": "07.03.2027", "masters": False},
    {"id": "t6", "nazwa": "Turniej 6", "data": "17.04.2027", "masters": False},
    {"id": "masters", "nazwa": "Masters (FINAŁ)", "data": "16.05.2027", "masters": True},
]

def turniej(tid: str) -> dict | None:
    return next((t for t in TURNIEJE if t["id"] == tid), None)

# --- Płcie --------------------------------------------------------------------
PLCIE: dict[str, str] = {"K": "Kobiety", "M": "Mężczyźni"}

# --- Punktacja (regulamin) ----------------------------------------------------
# Punkty do klasyfikacji generalnej za miejsce w grupie.
PUNKTY_ZA_MIEJSCE: dict[int, int] = {1: 30, 2: 20, 3: 15, 4: 10}
# Bonus za wygranie meczu „do zera" (przeciwnik 0 gemów).
BONUS_DO_ZERA: int = 2
# Ilu zawodników (osobno K i M) kwalifikuje się do turnieju Masters.
LIMIT_MASTERS: int = 8
# Docelowa liczebność grupy (każdy z każdym).
ROZMIAR_GRUPY: int = 4

# Listy rozwijane w rozpisce admina.
KORTY: list[str] = [f"Kort {i}" for i in range(1, 7)]           # Kort 1 … Kort 6
GODZINY: list[str] = [f"{h:02d}:{m:02d}"                        # 08:00 … 22:45 co 15 min
                      for h in range(8, 23) for m in (0, 15, 30, 45)]

# --- Nazwy zakładek arkusza Google / plików danych ----------------------------
WS_GRUPY = "grupy"
WS_MECZE = "mecze"

KOL_GRUPY = ["TurniejID", "Plec", "Grupa", "Zawodnik"]
KOL_MECZE = [
    "ID", "TurniejID", "Plec", "Grupa",
    "ZawodnikA", "ZawodnikB", "Kort", "Godzina", "GemyA", "GemyB",
]

# --- Sekrety / tryb danych ----------------------------------------------------
# Sekcja w st.secrets z ID arkusza cyklu (osobny arkusz niż liga).
SEKRET_ARKUSZ = "cykl_google_sheets"
SEKRET_KONTO = "gcp_service_account"   # współdzielone z ligą
SEKRET_ADMIN = "admin"                 # współdzielone z ligą ([admin].password)
