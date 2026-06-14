"""Szybkie testy czystej logiki (uruchom: python test_logic.py)."""

from liga_logic import BladWyniku, oblicz_mecz, oblicz_tabele, set_poprawny, super_tb_poprawny

bledy = []


def sprawdz(opis, warunek):
    print(("OK  " if warunek else "BŁĄD") + "  " + opis)
    if not warunek:
        bledy.append(opis)


def oczekuj_blad(opis, *a):
    try:
        oblicz_mecz(*a)
        sprawdz(opis + " (miał być błąd)", False)
    except BladWyniku:
        sprawdz(opis, True)


# --- poprawność setów ---
sprawdz("6:4 poprawny", set_poprawny(6, 4))
sprawdz("7:5 poprawny", set_poprawny(7, 5))
sprawdz("7:6 poprawny", set_poprawny(7, 6))
sprawdz("6:5 niepoprawny", not set_poprawny(6, 5))
sprawdz("6:6 niepoprawny", not set_poprawny(6, 6))
sprawdz("8:6 niepoprawny", not set_poprawny(8, 6))
sprawdz("super 10:7 ok", super_tb_poprawny(10, 7))
sprawdz("super 10:9 zły", not super_tb_poprawny(10, 9))

# --- wyniki meczów ---
r = oblicz_mecz("6:4", "6:3")
sprawdz("2:0 gospodarz", r["wynik"] == "2:0" and r["zwyciezca"] == "gospodarz"
        and r["gemy_g"] == 12 and r["gemy_o"] == 7)

r = oblicz_mecz("4:6", "2:6")
sprawdz("0:2 gość", r["wynik"] == "0:2" and r["zwyciezca"] == "gosc")

r = oblicz_mecz("6:4", "3:6", "10:7")
sprawdz("gemy bez super TB (6:4,3:6) = 9:10", r["gemy_g"] == 9 and r["gemy_o"] == 10)

r = oblicz_mecz("6:4", "3:6", "10:7")
sprawdz("2:1 gospodarz przez super TB", r["wynik"] == "2:1" and r["zwyciezca"] == "gospodarz")

r = oblicz_mecz("6:4", "3:6", "8:10")
sprawdz("1:2 gość przez super TB", r["wynik"] == "1:2" and r["zwyciezca"] == "gosc")

# --- błędy walidacji ---
oczekuj_blad("super TB przy 2:0 odrzucony", "6:4", "6:2", "10:5")
oczekuj_blad("brak super TB przy 1:1 odrzucony", "6:4", "3:6", "")
oczekuj_blad("zły set odrzucony", "6:5", "6:3")
oczekuj_blad("zły super TB odrzucony", "6:4", "3:6", "10:9")

# --- tabela ---
mecze = [
    {"Gospodarz": "Ala", "Gość": "Ola", "Set1": "6:4", "Set2": "6:2", "SuperTB": ""},
    {"Gospodarz": "Ola", "Gość": "Ela", "Set1": "6:3", "Set2": "4:6", "SuperTB": "10:8"},
    {"Gospodarz": "Ala", "Gość": "Ela", "Set1": "2:6", "Set2": "1:6", "SuperTB": ""},
]
t = oblicz_tabele(mecze)
print(t.to_string(index=False))
# Ala: 2 mecze (W vs Ola, P vs Ela) -> 2 pkt
# Ola: 2 mecze (P vs Ala, W vs Ela) -> 2 pkt
# Ela: 2 mecze (P vs Ola, W vs Ala) -> 2 pkt
sprawdz("3 zawodników w tabeli", len(t) == 3)
sprawdz("każdy ma 2 pkt", set(t["Punkty"]) == {2})
sprawdz("Ala ma 2 mecze", int(t[t.Zawodnik == "Ala"]["Mecze"].iloc[0]) == 2)
# Ola: sety wygrane = 2(vs Ala?nie) ... sprawdźmy bilans Eli (wygrała z Alą 2:0, przegrała z Olą 1:2) -> sety 3:2 bilans +1
ela = t[t.Zawodnik == "Ela"].iloc[0]
sprawdz("Ela sety 3 wygrane / 2 przegrane", int(ela["Sety wygrane"]) == 3 and int(ela["Sety przegrane"]) == 2)
sprawdz("tabela ma kolumny gemów", "Gemy wygrane" in t.columns and "Gemy przegrane" in t.columns)

print()
if bledy:
    print(f"NIEPOWODZENIA: {len(bledy)}")
    raise SystemExit(1)
print("Wszystkie testy przeszly OK")
