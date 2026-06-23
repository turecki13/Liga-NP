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
    page_title="Letnia Liga Tenisowa NP Tennis Academy",
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


def _tabela_statyczna(df: pd.DataFrame) -> None:
    """Statyczna tabela – nie da się przesuwać ani sortować kolumn. Bez indeksu."""
    df = df.copy()
    df.index = [""] * len(df)
    st.table(df)


def _pauzy_wg_kolejki(df: pd.DataFrame) -> dict:
    """Zwraca {kolejka: [pauzujący]} na podstawie pełnego terminarza ligi."""
    if "Kolejka" not in df.columns:
        return {}

    def osoby(ramka) -> set:
        zbior = set()
        for kol in ("Gospodarz", "Gość"):
            if kol in ramka.columns:
                zbior |= {str(x).strip() for x in ramka[kol] if str(x).strip()}
        return zbior

    wszyscy = osoby(df)
    pauzy = {}
    for kolejka, grupa in df.groupby("Kolejka", sort=True):
        nieobecni = sorted(wszyscy - osoby(grupa))
        if nieobecni:
            pauzy[kolejka] = nieobecni
    return pauzy


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
            _kalendarz_sheets(mecze, oczekujace_id, nazwa_ligi)
    else:
        prefiks = _prefiks_csv(nazwa_ligi)
        with tab_tabela:
            df = _wczytaj_csv(f"{prefiks}_tabela.csv")
            if df is None or df.empty:
                st.info("Brak danych w tabeli.")
            else:
                st.table(_tabela_z_pozycjami(df, "Punkty"))
        with tab_kalendarz:
            df = _wczytaj_csv(f"{prefiks}_mecze.csv")
            _kalendarz_csv(df)


def _tabela_sheets(mecze: list[dict]) -> None:
    zatwierdzone = [m for m in mecze if str(m.get("Zatwierdzono", "")).strip()]
    tabela = liga_logic.oblicz_tabele(zatwierdzone)
    if tabela.empty:
        st.info("Brak zatwierdzonych wyników – tabela pojawi się po akceptacji pierwszych meczów.")
        return
    st.table(_tabela_z_pozycjami(tabela))
    st.caption("Tabela liczona automatycznie z zatwierdzonych wyników.")


def _lista_zawodnikow(df: pd.DataFrame) -> list[str]:
    """Posortowana lista unikalnych zawodników z kolumn Gospodarz/Gość."""
    nazwy = set()
    for kol in ("Gospodarz", "Gość"):
        if kol in df.columns:
            nazwy |= {str(x).strip() for x in df[kol] if str(x).strip()}
    return sorted(nazwy)


def _kalendarz_sheets(mecze: list[dict], oczekujace_id: set[str], klucz: str) -> None:
    if not mecze:
        st.info("Brak meczów w arkuszu dla tej ligi.")
        return
    df = pd.DataFrame(mecze)

    def status(r):
        wynik = str(r.get("Wynik", "")).strip()
        if wynik:
            sety = [str(r.get(k, "")).strip() for k in ("Set1", "Set2", "SuperTB")]
            sety = [s for s in sety if s]
            return f"{wynik} ({', '.join(sety)})" if sety else wynik
        if str(r.get("ID", "")).strip() in oczekujace_id:
            return "⏳ oczekuje na akceptację"
        return "—"

    df["Wynik"] = df.apply(status, axis=1)
    pauzy = _pauzy_wg_kolejki(df)  # z pełnego terminarza, zanim zadziała filtr

    # Filtr po zawodniku – pokaż tylko jego mecze i kolejki.
    WSZYSCY = "— wszyscy zawodnicy —"
    wybor = st.selectbox("Pokaż mecze zawodnika:", [WSZYSCY] + _lista_zawodnikow(df),
                         key=f"filtr_kal_{klucz}")
    if wybor != WSZYSCY:
        df = df[(df["Gospodarz"] == wybor) | (df["Gość"] == wybor)]
        if df.empty:
            st.info("Brak meczów tego zawodnika.")
            return

    kolumny = [k for k in ["Data", "Gospodarz", "Gość", "Wynik"] if k in df.columns]
    if "Kolejka" in df.columns:
        for kolejka, grupa in df.groupby("Kolejka", sort=True):
            st.markdown(f"#### Kolejka {kolejka}")
            _tabela_statyczna(grupa[kolumny])
            if pauzy.get(kolejka):
                st.caption("⏸️ Pauzuje: " + ", ".join(pauzy[kolejka]))
    else:
        _tabela_statyczna(df[kolumny])


def _kalendarz_csv(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info("Brak zaplanowanych meczów.")
        return
    df = df.drop(columns=[c for c in ["Godzina"] if c in df.columns])
    pauzy = _pauzy_wg_kolejki(df)
    if "Kolejka" in df.columns:
        for kolejka, grupa in df.groupby("Kolejka", sort=True):
            st.markdown(f"#### Kolejka {kolejka}")
            _tabela_statyczna(grupa.drop(columns=["Kolejka"]))
            if pauzy.get(kolejka):
                st.caption("⏸️ Pauzuje: " + ", ".join(pauzy[kolejka]))
    else:
        _tabela_statyczna(df)


# =============================================================================
#  Strona główna, Fair Play
# =============================================================================
def strona_glowna() -> None:
    if LOGO_PIONOWE.exists():
        kol_logo, kol_tytul = st.columns([1, 3], vertical_alignment="center")
        kol_logo.image(str(LOGO_PIONOWE), width=180)
        kol_tytul.title("Letnia Liga Tenisowa NP Tennis Academy")
    else:
        st.title("🎾 Letnia Liga Tenisowa NP Tennis Academy")

    st.markdown(
        """
        Witamy na oficjalnej stronie **Letniej Ligi Tenisowej NP Tennis Academy**!

        Strona prezentuje aktualne tabele oraz terminarze rozgrywek we wszystkich
        kategoriach. Wybierz odpowiednią ligę z menu po lewej stronie.
        """
    )

    if sheets.skonfigurowane():
        st.success("✅ Wyniki możesz zgłaszać samodzielnie w zakładce **➕ Zgłoś wynik** "
                   "(każdy wynik trafia do akceptacji organizatora).")
        st.success("🤝 Zachęcamy do aktywnego korzystania z zakładki **Klasyfikacja Fair Play** "
                   "— (d)oceniajcie przeciwników i budujmy razem dobrą, sportową atmosferę w lidze!")
    else:
        st.warning("ℹ️ Tryb tylko do odczytu (dane z plików CSV). Aby włączyć samodzielne "
                   "zgłaszanie wyników, skonfiguruj Google Sheets – patrz README.")

    tab_zalegle, tab_regulamin = st.tabs(["⏳ Zaległe mecze", "📜 Regulamin"])

    with tab_zalegle:
        _zalegle_mecze()

    with tab_regulamin:
        st.subheader("ℹ️ Informacje")
        st.markdown(
            """
            - **Sezon:** 2026 (15.06 – 20.09)
            - **Format:** rozgrywki w systemie ligowym (każdy z każdym)
            - **Mecz:** do 2 wygranych setów; przy stanie 1:1 super tie-break do 10
            - **Punktacja:** 3 pkt za zwycięstwo, 1 pkt za porażkę
            - **Kategorie:** 3 ligi kobiet i 3 ligi mężczyzn + klasyfikacja Fair Play
            """
        )
        st.subheader("📜 Regulamin")
        regulamin = DATA_DIR / "regulamin.md"
        if regulamin.exists():
            st.markdown(regulamin.read_text(encoding="utf-8"))
        else:
            st.info("Treść regulaminu znajdziesz w pliku `data/regulamin.md`.")

    st.markdown("---")
    st.caption("© 2026 Letnia Liga Tenisowa NP Tennis Academy · "
               "aplikację stworzył **Tomek Turek** 🎾")


def _zalegle_do_kolejki() -> int:
    """Do której kolejki włącznie pokazujemy zaległe (sterowane przez admina)."""
    if not sheets.skonfigurowane():
        return 1
    wart = sheets.pobierz_ustawienia().get(config.KLUCZ_ZALEGLE_DO_KOLEJKI, "1")
    try:
        return max(1, int(float(wart)))
    except (TypeError, ValueError):
        return 1


def _zalegle_mecze() -> None:
    """Zaległe mecze (bez wyniku) do wskazanej kolejki – z podziałem na kolejki."""
    if not sheets.skonfigurowane():
        st.info("Sekcja dostępna po włączeniu Google Sheets.")
        return
    mecze = sheets.pobierz_mecze()
    if not mecze:
        st.info("Brak meczów w arkuszu.")
        return

    do_kolejki = _zalegle_do_kolejki()
    st.caption(f"Pokazywane zaległości z kolejek: 1–{do_kolejki} "
               "(kolejne odsłania organizator).")

    WYBIERZ = "— wybierz ligę —"
    liga = st.selectbox("Wybierz ligę", [WYBIERZ] + list(config.LIGI.values()), key="zal_liga")
    if liga == WYBIERZ:
        st.info("Wybierz ligę, aby zobaczyć zaległe mecze.")
        return

    oczek = {
        str(z.get("MeczID", "")).strip()
        for z in sheets.pobierz_zgloszenia()
        if str(z.get("Status", "")).strip() == config.STATUS_OCZEKUJE
    }

    def jako_int(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0

    zalegle = []
    for mm in mecze:
        if str(mm.get("Liga", "")).strip() != liga:
            continue
        if jako_int(mm.get("Kolejka")) > do_kolejki:
            continue  # ta kolejka nie jest jeszcze odsłonięta
        if str(mm.get("Wynik", "")).strip() or str(mm.get("Zatwierdzono", "")).strip():
            continue  # mecz rozegrany
        oczekuje = str(mm.get("ID", "")).strip() in oczek
        zalegle.append({
            "Kolejka": mm.get("Kolejka"),
            "Gospodarz": mm.get("Gospodarz"),
            "Gość": mm.get("Gość"),
            "Termin": mm.get("Data"),
            "Status": "⏳ oczekuje na akceptację" if oczekuje else "❗ nierozegrany",
        })

    if not zalegle:
        st.success("🎉 Brak zaległych meczów w tej lidze!")
        return

    df = pd.DataFrame(zalegle)
    for kolejka, grupa in df.groupby("Kolejka", sort=True):
        st.markdown(f"#### Kolejka {kolejka}")
        _tabela_statyczna(grupa[["Gospodarz", "Gość", "Termin", "Status"]])


# Etykiety ocen fair play (-1 / 0 / +1) — kolejność od najlepszej.
OCENY_FP = {
    1: "🟢 +1 — bardzo sportowo",
    0: "⚪ 0 — normalnie",
    -1: "🔴 -1 — niesportowo",
}


def strona_fairplay() -> None:
    st.header("🤝 Klasyfikacja Fair Play")
    if sheets.skonfigurowane():
        tab_ocena, tab_tabela = st.tabs(["➕ Dodaj ocenę", "📊 Tabela Fair Play"])
        with tab_ocena:
            st.caption("Po rozegranym meczu oceń przeciwnika. "
                       "Przy ocenie -1 komentarz jest obowiązkowy.")
            _formularz_oceny_fp()
        with tab_tabela:
            _tabela_fairplay()
    else:
        _tabela_fairplay()


def _int0(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _fairplay_z_ocen() -> pd.DataFrame | None:
    """Buduje klasyfikację Fair Play: punkty = suma ocen (-1/0/+1) zawodnika."""
    roster = sheets.pobierz_fairplay()   # Zawodnik, Liga (pełna lista uczestników)
    oceny = sheets.pobierz_oceny()

    suma, liczba = {}, {}
    for o in oceny:
        naz = str(o.get("Oceniany", "")).strip()
        if not naz:
            continue
        suma[naz] = suma.get(naz, 0) + _int0(o.get("Ocena"))
        liczba[naz] = liczba.get(naz, 0) + 1

    wiersze = []
    if roster:
        for r in roster:
            naz = str(r.get("Zawodnik", "")).strip()
            if not naz:
                continue
            wiersze.append({"Zawodnik": naz, "Liga": str(r.get("Liga", "")).strip(),
                            "Punkty Fair Play": suma.get(naz, 0), "Liczba ocen": liczba.get(naz, 0)})
    else:  # brak rosteru – zbuduj listę z samych ocen
        ligi = {}
        for o in oceny:
            naz = str(o.get("Oceniany", "")).strip()
            if naz:
                ligi.setdefault(naz, str(o.get("Liga", "")).strip())
        for naz, lg in ligi.items():
            wiersze.append({"Zawodnik": naz, "Liga": lg,
                            "Punkty Fair Play": suma.get(naz, 0), "Liczba ocen": liczba.get(naz, 0)})

    return pd.DataFrame(wiersze) if wiersze else None


def _tabela_fairplay() -> None:
    if sheets.skonfigurowane():
        df = _fairplay_z_ocen()
    else:
        df = _wczytaj_csv("fairplay.csv")

    if df is None or df.empty:
        st.info("Brak danych klasyfikacji Fair Play.")
        return

    # Filtry: liga + szukaj zawodnika (pozycje liczone w obrębie wybranej ligi).
    WSZYSTKIE = "— wszystkie ligi —"
    ligi = [WSZYSTKIE] + (sorted(df["Liga"].dropna().unique()) if "Liga" in df.columns else [])
    c1, c2 = st.columns(2)
    liga = c1.selectbox("Liga", ligi, key="fp_liga")
    szukaj = c2.text_input("Szukaj zawodnika", key="fp_szukaj").strip()

    zakres = df if liga == WSZYSTKIE else df[df["Liga"] == liga]
    ranking = _tabela_z_pozycjami(zakres, "Punkty Fair Play")
    if szukaj:
        ranking = ranking[ranking["Zawodnik"].str.contains(szukaj, case=False, na=False)]
    if ranking.empty:
        st.info("Brak zawodników dla wybranych filtrów.")
    else:
        st.table(ranking)


def _formularz_oceny_fp() -> None:
    mecze = sheets.pobierz_mecze()
    liga = st.selectbox("Liga", list(config.LIGI.values()), key="oc_liga")
    gracze = sorted({str(m.get("Gospodarz", "")).strip() for m in mecze
                     if str(m.get("Liga", "")).strip() == liga}
                    | {str(m.get("Gość", "")).strip() for m in mecze
                       if str(m.get("Liga", "")).strip() == liga})
    gracze = [g for g in gracze if g]
    if not gracze:
        st.info("Brak zawodników w tej lidze.")
        return

    ja = st.selectbox("Twoje nazwisko", gracze, key="oc_ja")
    moje = [m for m in mecze
            if str(m.get("Liga", "")).strip() == liga
            and ja in (str(m.get("Gospodarz", "")).strip(), str(m.get("Gość", "")).strip())]
    if not moje:
        st.info("Brak meczów dla tego zawodnika.")
        return

    def przeciwnik(m):
        g, go = str(m.get("Gospodarz", "")).strip(), str(m.get("Gość", "")).strip()
        return go if ja == g else g

    wybrany = st.selectbox(
        "Mecz (oceniasz przeciwnika)", moje,
        format_func=lambda m: f"Kolejka {m.get('Kolejka','?')}: vs {przeciwnik(m)}",
        key="oc_mecz",
    )
    oceniany = przeciwnik(wybrany)
    st.markdown(f"Oceniasz: **{oceniany}**")

    with st.form("formularz_oceny"):
        ocena_label = st.radio("Ocena fair play", list(OCENY_FP.values()), index=1)
        komentarz = st.text_area("Komentarz", placeholder="Opcjonalnie (przy ocenie -1 wymagany)")
        wyslij = st.form_submit_button("Wyślij ocenę", type="primary")

    if wyslij:
        ocena = next(k for k, v in OCENY_FP.items() if v == ocena_label)
        if ocena == -1 and not komentarz.strip():
            st.error("❌ Przy ocenie -1 komentarz jest obowiązkowy (zgodnie z regulaminem).")
            return
        wpis = {
            "ID": uuid4().hex[:8],
            "Czas": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "MeczID": wybrany.get("ID", ""),
            "Liga": liga,
            "Kolejka": wybrany.get("Kolejka", ""),
            "Oceniający": ja,
            "Oceniany": oceniany,
            "Ocena": ocena,
            "Komentarz": komentarz.strip(),
        }
        try:
            sheets.dodaj_ocene(wpis)
        except Exception as e:
            st.error(f"Nie udało się zapisać oceny: {e}")
            return
        st.success(f"✅ Zapisano ocenę fair play dla: {oceniany}. Dziękujemy!")


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

    # Filtr po zawodniku – ułatwia znalezienie swojego meczu.
    WSZYSCY = "— wszyscy zawodnicy —"
    gracze = sorted({str(m.get("Gospodarz", "")).strip() for m in dostepne}
                    | {str(m.get("Gość", "")).strip() for m in dostepne})
    kto = st.selectbox("Twoje nazwisko (filtr)", [WSZYSCY] + gracze)
    if kto != WSZYSCY:
        dostepne = [m for m in dostepne
                    if kto in (str(m.get("Gospodarz", "")).strip(), str(m.get("Gość", "")).strip())]

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

    _panel_zalegle_admin()

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

    _panel_oceny_fp()


def _panel_zalegle_admin() -> None:
    st.subheader("🗓️ Zaległe mecze — widoczne kolejki")
    n = _zalegle_do_kolejki()
    st.write(f"Na stronie głównej pokazywane są zaległości z kolejek **1–{n}**.")
    c1, c2 = st.columns(2)
    if c1.button(f"➕ Odsłoń zaległe z kolejki {n + 1}", type="primary", disabled=n >= 14):
        try:
            sheets.ustaw_ustawienie(config.KLUCZ_ZALEGLE_DO_KOLEJKI, n + 1)
            st.toast(f"Odsłonięto zaległości do kolejki {n + 1}.")
            st.rerun()
        except Exception as e:
            st.error(f"Błąd: {e}")
    if c2.button("↩️ Reset do kolejki 1", disabled=n <= 1):
        try:
            sheets.ustaw_ustawienie(config.KLUCZ_ZALEGLE_DO_KOLEJKI, 1)
            st.toast("Zresetowano do kolejki 1.")
            st.rerun()
        except Exception as e:
            st.error(f"Błąd: {e}")
    st.markdown("---")


def _panel_oceny_fp() -> None:
    st.markdown("---")
    oceny = sheets.pobierz_oceny()
    st.subheader(f"🤝 Oceny fair play: {len(oceny)}")
    if not oceny:
        st.info("Brak ocen fair play.")
        return

    WSZYSTKIE = "— wszystkie ligi —"
    ligi = [WSZYSTKIE] + sorted({str(o.get("Liga", "")).strip() for o in oceny if str(o.get("Liga", "")).strip()})
    c1, c2 = st.columns(2)
    liga = c1.selectbox("Liga", ligi, key="adm_oc_liga")
    tylko_neg = c2.checkbox("Tylko negatywne (-1)", key="adm_oc_neg")

    def jako_int(v):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0

    widoczne = oceny
    if liga != WSZYSTKIE:
        widoczne = [o for o in widoczne if str(o.get("Liga", "")).strip() == liga]
    if tylko_neg:
        widoczne = [o for o in widoczne if jako_int(o.get("Ocena")) == -1]
    widoczne = sorted(widoczne, key=lambda o: str(o.get("Czas", "")), reverse=True)

    if not widoczne:
        st.info("Brak ocen dla wybranych filtrów.")
        return

    for i, o in enumerate(widoczne):
        ocena = jako_int(o.get("Ocena"))
        etykieta = OCENY_FP.get(ocena, str(ocena))
        oid = str(o.get("ID", "")).strip()
        with st.container(border=True):
            st.markdown(f"{etykieta} — **{o.get('Oceniany','')}**  ·  od: {o.get('Oceniający','')}")
            st.caption(
                f"{o.get('Liga','')} · Kolejka {o.get('Kolejka','')} · {o.get('Czas','')}"
            )
            komentarz = str(o.get("Komentarz", "")).strip()
            if komentarz:
                st.markdown(f"> {komentarz}")
            if oid and st.button("🗑️ Usuń ocenę", key=f"del_oc_{oid}_{i}"):
                try:
                    sheets.usun_ocene(oid)
                    st.toast("Ocena usunięta.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd usuwania: {e}")


# =============================================================================
#  Nawigacja
# =============================================================================
def main() -> None:
    st.sidebar.title("Menu")

    opcje = ["🏠 Strona główna"] + list(LIGI_MENU.keys()) + ["🤝 Klasyfikacja Fair Play"]
    if sheets.skonfigurowane():
        opcje += ["➕ Zgłoś wynik", "🔒 Panel akceptacji"]

    wybor = st.sidebar.radio("Przejdź do:", opcje, label_visibility="collapsed")

    try:
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
    except Exception as e:
        # Czytelny komunikat dla użytkowników zamiast surowego tracebacku.
        if sheets.skonfigurowane():
            st.error(
                "⚠️ Nie udało się połączyć z arkuszem Google. Spróbuj odświeżyć stronę "
                "za chwilę. Jeśli problem się powtarza, skontaktuj się z organizatorem."
            )
            st.caption("Najczęstsza przyczyna: błędne dane konta usługi w sekretach "
                       "albo arkusz nieudostępniony kontu usługi.")
            with st.expander("Szczegóły techniczne (dla organizatora)"):
                st.exception(e)
        else:
            raise

    st.sidebar.markdown("---")
    st.sidebar.caption("Letnia Liga Tenisowa • NP Tennis Academy • sezon 2026")
    st.sidebar.caption("Aplikację stworzył **Tomek Turek** 🎾")


main()
