"""
Liga Tenisowa – strona prezentacyjna (Streamlit) z samodzielnym zgłaszaniem
wyników i trybem akceptacji przez administratora.

Uruchomienie:
    streamlit run app.py

Tryby działania:
  • Google Sheets (gdy ustawione sekrety) – tabele liczone automatycznie
    z ZATWIERDZONYCH wyników, zawodnicy zgłaszają wyniki, admin akceptuje.
  • CSV (gdy brak sekretów) – dane tylko do odczytu z folderu ./data.
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

import config
import liga_logic
import sheets

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGO_DIR = BASE_DIR / "logo"
LOGO_POZIOME = LOGO_DIR / "logo 2.png"   # ikona + napis obok siebie
LOGO_PIONOWE = LOGO_DIR / "logo 1.png"   # ikona nad napisem

# Etykieta w menu -> klucz/nazwa ligi
LIGI_MENU = {f"🎾 {nazwa}": nazwa for nazwa in config.LIGI.values()}

st.set_page_config(
    page_title="Liga Tenisowa – NP Tennis Academy",
    page_icon=str(LOGO_PIONOWE) if LOGO_PIONOWE.exists() else "🎾",
    layout="wide",
)

if LOGO_POZIOME.exists():
    st.logo(str(LOGO_POZIOME), icon_image=str(LOGO_PIONOWE), size="large")


# =============================================================================
#  Pomocnicze – wyświetlanie
# =============================================================================
def _tabela_z_pozycjami(df: pd.DataFrame, kol_sort: str | None = None) -> pd.DataFrame:
    if kol_sort and kol_sort in df.columns:
        df = df.sort_values(kol_sort, ascending=False, kind="stable").reset_index(drop=True)
    df = df.copy()
    df.index = range(1, len(df) + 1)
    df.index.name = "Poz."
    return df


# =============================================================================
#  Odczyt danych – CSV (tryb zapasowy)
# =============================================================================
@st.cache_data
def _wczytaj_csv(nazwa_pliku: str) -> pd.DataFrame | None:
    sciezka = DATA_DIR / nazwa_pliku
    return pd.read_csv(sciezka) if sciezka.exists() else None


def _prefiks_csv(nazwa_ligi: str) -> str:
    klucz = next(k for k, v in config.LIGI.items() if v == nazwa_ligi)
    return f"liga_{klucz}"


# =============================================================================
#  Strony lig
# =============================================================================
def strona_ligi(etykieta_menu: str, nazwa_ligi: str) -> None:
    st.header(f"🎾 {nazwa_ligi}")
    tab_tabela, tab_kalendarz = st.tabs(["📊 Tabela główna", "🗓️ Kalendarz kolejek"])

    if sheets.skonfigurowane():
        mecze = [m for m in sheets.pobierz_mecze() if str(m.get("Liga", "")).strip() == nazwa_ligi]
        zgloszenia = sheets.pobierz_zgloszenia()
        oczekujace_id = {
            str(z.get("MeczID", "")).strip()
            for z in zgloszenia
            if str(z.get("Status", "")).strip() == config.STATUS_OCZEKUJE
        }
        with tab_tabela:
            _tabela_sheets(mecze)
        with tab_kalendarz:
            _kalendarz_sheets(mecze, oczekujace_id)
    else:
        prefiks = _prefiks_csv(nazwa_ligi)
        with tab_tabela:
            df = _wczytaj_csv(f"{prefiks}_tabela.csv")
            if df is None or df.empty:
                st.info("Brak danych w tabeli.")
            else:
                st.dataframe(_tabela_z_pozycjami(df, "Punkty"), use_container_width=True)
        with tab_kalendarz:
            df = _wczytaj_csv(f"{prefiks}_mecze.csv")
            _kalendarz_csv(df)


def _tabela_sheets(mecze: list[dict]) -> None:
    zatwierdzone = [m for m in mecze if str(m.get("Zatwierdzono", "")).strip()]
    tabela = liga_logic.oblicz_tabele(zatwierdzone)
    if tabela.empty:
        st.info("Brak zatwierdzonych wyników – tabela pojawi się po akceptacji pierwszych meczów.")
        return
    st.dataframe(_tabela_z_pozycjami(tabela), use_container_width=True)
    st.caption("Tabela liczona automatycznie z zatwierdzonych wyników.")


def _kalendarz_sheets(mecze: list[dict], oczekujace_id: set[str]) -> None:
    if not mecze:
        st.info("Brak meczów w arkuszu dla tej ligi.")
        return
    df = pd.DataFrame(mecze)

    def status(r):
        if str(r.get("Wynik", "")).strip():
            return str(r["Wynik"])
        if str(r.get("ID", "")).strip() in oczekujace_id:
            return "⏳ oczekuje na akceptację"
        return "—"

    df["Wynik"] = df.apply(status, axis=1)
    kolumny = [k for k in ["Data", "Gospodarz", "Gość", "Wynik"] if k in df.columns]

    if "Kolejka" in df.columns:
        for kolejka, grupa in df.groupby("Kolejka", sort=True):
            st.markdown(f"#### Kolejka {kolejka}")
            st.dataframe(grupa[kolumny].reset_index(drop=True),
                         use_container_width=True, hide_index=True)
    else:
        st.dataframe(df[kolumny], use_container_width=True, hide_index=True)


def _kalendarz_csv(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info("Brak zaplanowanych meczów.")
        return
    df = df.drop(columns=[c for c in ["Godzina"] if c in df.columns])
    if "Kolejka" in df.columns:
        for kolejka, grupa in df.groupby("Kolejka", sort=True):
            st.markdown(f"#### Kolejka {kolejka}")
            st.dataframe(grupa.drop(columns=["Kolejka"]).reset_index(drop=True),
                         use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


# =============================================================================
#  Strona główna, Fair Play
# =============================================================================
def strona_glowna() -> None:
    if LOGO_PIONOWE.exists():
        kol_logo, kol_tytul = st.columns([1, 3], vertical_alignment="center")
        kol_logo.image(str(LOGO_PIONOWE), width=180)
        kol_tytul.title("Liga Tenisowa")
    else:
        st.title("🎾 Liga Tenisowa")

    st.markdown(
        """
        Witamy na oficjalnej stronie **Ligi Tenisowej NP Tennis Academy**!

        Strona prezentuje aktualne tabele oraz terminarze rozgrywek we wszystkich
        kategoriach. Wybierz odpowiednią ligę z menu po lewej stronie.
        """
    )

    if sheets.skonfigurowane():
        st.success("✅ Wyniki możesz zgłaszać samodzielnie w zakładce **➕ Zgłoś wynik** "
                   "(każdy wynik trafia do akceptacji organizatora).")
    else:
        st.warning("ℹ️ Tryb tylko do odczytu (dane z plików CSV). Aby włączyć samodzielne "
                   "zgłaszanie wyników, skonfiguruj Google Sheets – patrz README.")

    st.subheader("ℹ️ Informacje")
    st.markdown(
        """
        - **Sezon:** 2026
        - **Format:** rozgrywki w systemie ligowym (każdy z każdym)
        - **Mecz:** do 2 wygranych setów; przy stanie 1:1 super tie-break do 10
        - **Punktacja:** 2 pkt za zwycięstwo, 0 za porażkę
        - **Kategorie:** 3 ligi kobiet i 3 ligi mężczyzn + klasyfikacja Fair Play
        """
    )

    st.subheader("📜 Regulamin")
    regulamin = DATA_DIR / "regulamin.md"
    if regulamin.exists():
        st.markdown(regulamin.read_text(encoding="utf-8"))
    else:
        st.info("Treść regulaminu znajdziesz w pliku `data/regulamin.md`.")


def strona_fairplay() -> None:
    st.header("🤝 Klasyfikacja Fair Play")
    if sheets.skonfigurowane():
        dane = sheets.pobierz_fairplay()
        df = pd.DataFrame(dane) if dane else None
    else:
        df = _wczytaj_csv("fairplay.csv")
    if df is None or df.empty:
        st.info("Brak danych klasyfikacji Fair Play.")
        return
    st.dataframe(_tabela_z_pozycjami(df, "Punkty Fair Play"), use_container_width=True)


# =============================================================================
#  Zgłaszanie wyniku (tryb Google Sheets)
# =============================================================================
def strona_zglos_wynik() -> None:
    st.header("➕ Zgłoś wynik meczu")
    st.caption("Wynik trafia do akceptacji organizatora i pojawi się w tabeli po zatwierdzeniu.")

    mecze = sheets.pobierz_mecze()
    nazwa_ligi = st.selectbox("Liga", list(config.LIGI.values()))

    # Mecze danej ligi bez zatwierdzonego wyniku.
    dostepne = [
        m for m in mecze
        if str(m.get("Liga", "")).strip() == nazwa_ligi
        and not str(m.get("Zatwierdzono", "")).strip()
    ]
    if not dostepne:
        st.info("Brak meczów do zgłoszenia w tej lidze (wszystkie rozegrane lub arkusz pusty).")
        return

    def etykieta(m):
        return f"Kolejka {m.get('Kolejka','?')}: {m.get('Gospodarz','?')} vs {m.get('Gość','?')}" \
               f"  ({m.get('Data','')})"

    wybrany = st.selectbox("Mecz", dostepne, format_func=etykieta)

    st.markdown(f"**{wybrany.get('Gospodarz','?')}** (gospodarz)  vs  **{wybrany.get('Gość','?')}** (gość)")
    st.caption("Wpisuj wynik z perspektywy gospodarza, np. 6:4. Super tie-break tylko przy stanie 1:1.")

    with st.form("formularz_wyniku"):
        c1, c2, c3 = st.columns(3)
        set1 = c1.text_input("Set 1", placeholder="6:4")
        set2 = c2.text_input("Set 2", placeholder="3:6")
        stb = c3.text_input("Super tie-break (jeśli 1:1)", placeholder="10:7")
        wyslij = st.form_submit_button("Wyślij do akceptacji", type="primary")

    if wyslij:
        try:
            wynik = liga_logic.oblicz_mecz(set1, set2, stb)
        except liga_logic.BladWyniku as e:
            st.error(f"❌ {e}")
            return

        zgloszenie = {
            "ID": uuid4().hex[:8],
            "Czas": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "MeczID": wybrany.get("ID", ""),
            "Liga": nazwa_ligi,
            "Kolejka": wybrany.get("Kolejka", ""),
            "Gospodarz": wybrany.get("Gospodarz", ""),
            "Gość": wybrany.get("Gość", ""),
            "Set1": set1.strip(),
            "Set2": set2.strip(),
            "SuperTB": stb.strip(),
            "Wynik": wynik["wynik"],
            "Status": config.STATUS_OCZEKUJE,
            "Rozpatrzono": "",
        }
        try:
            sheets.dodaj_zgloszenie(zgloszenie)
        except Exception as e:
            st.error(f"Nie udało się zapisać zgłoszenia: {e}")
            return
        st.success(f"✅ Zgłoszono wynik {wynik['wynik']}. Czeka na akceptację organizatora. Dziękujemy!")
        st.balloons()


# =============================================================================
#  Panel akceptacji (admin)
# =============================================================================
def strona_panel_admina() -> None:
    st.header("🔒 Panel akceptacji")
    haslo_ok = sheets.haslo_admina()

    if not st.session_state.get("admin_zalogowany"):
        with st.form("login"):
            podane = st.text_input("Hasło administratora", type="password")
            if st.form_submit_button("Zaloguj"):
                if haslo_ok and podane == haslo_ok:
                    st.session_state["admin_zalogowany"] = True
                    st.rerun()
                else:
                    st.error("Błędne hasło.")
        return

    col_a, col_b = st.columns([4, 1])
    col_a.success("Zalogowano jako administrator.")
    if col_b.button("Wyloguj"):
        st.session_state["admin_zalogowany"] = False
        st.rerun()

    zgloszenia = sheets.pobierz_zgloszenia()
    oczekujace = [z for z in zgloszenia if str(z.get("Status", "")).strip() == config.STATUS_OCZEKUJE]

    st.subheader(f"Oczekujące zgłoszenia: {len(oczekujace)}")
    if not oczekujace:
        st.info("Brak zgłoszeń do rozpatrzenia.")
    for z in oczekujace:
        with st.container(border=True):
            st.markdown(
                f"**{z.get('Liga','')}** · Kolejka {z.get('Kolejka','')} · "
                f"{z.get('Gospodarz','')} vs {z.get('Gość','')}"
            )
            st.markdown(
                f"Wynik: **{z.get('Wynik','')}**  "
                f"(sety: {z.get('Set1','')}, {z.get('Set2','')}"
                + (f", super TB: {z.get('SuperTB','')}" if str(z.get('SuperTB','')).strip() else "")
                + f") · zgłoszono {z.get('Czas','')}"
            )
            c1, c2, _ = st.columns([1, 1, 4])
            if c1.button("✅ Akceptuj", key=f"akc_{z['ID']}", type="primary"):
                try:
                    sheets.akceptuj_zgloszenie(z)
                    st.toast("Zaakceptowano i zapisano do tabeli.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd akceptacji: {e}")
            if c2.button("❌ Odrzuć", key=f"odrz_{z['ID']}"):
                try:
                    sheets.odrzuc_zgloszenie(z)
                    st.toast("Zgłoszenie odrzucone.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd: {e}")


# =============================================================================
#  Nawigacja
# =============================================================================
def main() -> None:
    st.sidebar.title("Menu")

    opcje = ["🏠 Strona główna"] + list(LIGI_MENU.keys()) + ["🤝 Klasyfikacja Fair Play"]
    if sheets.skonfigurowane():
        opcje += ["➕ Zgłoś wynik", "🔒 Panel akceptacji"]

    wybor = st.sidebar.radio("Przejdź do:", opcje, label_visibility="collapsed")

    if wybor == "🏠 Strona główna":
        strona_glowna()
    elif wybor == "🤝 Klasyfikacja Fair Play":
        strona_fairplay()
    elif wybor == "➕ Zgłoś wynik":
        strona_zglos_wynik()
    elif wybor == "🔒 Panel akceptacji":
        strona_panel_admina()
    elif wybor in LIGI_MENU:
        strona_ligi(wybor, LIGI_MENU[wybor])

    st.sidebar.markdown("---")
    st.sidebar.caption("Liga Tenisowa • NP Tennis Academy • sezon 2026")


main()
