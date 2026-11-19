"""
Cykl Turniejów Singlowych NP Tennis Academy — aplikacja (Streamlit).

Uruchomienie:
    streamlit run app_cykl.py

Niezależna od Letniej Ligi (app.py). Publicznie widoczna, edycja tylko po
zalogowaniu administratora (korty, godziny, wyniki, składy grup).

Tryby danych:
  • Google Sheets — gdy skonfigurowany arkusz cyklu w .streamlit/secrets.toml,
  • lokalny JSON (data/cykl/) — w przeciwnym razie (podgląd i testy bez arkusza).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import cykl_config as C
import cykl_logic
import cykl_store as store

BASE_DIR = Path(__file__).parent
LOGO_DIR = BASE_DIR / "logo"
LOGO_POZIOME = LOGO_DIR / "logo 2.png"
LOGO_PIONOWE = LOGO_DIR / "logo 1.png"

st.set_page_config(
    page_title="Cykl Turniejów Singlowych NP Tennis Academy",
    page_icon=str(LOGO_PIONOWE) if LOGO_PIONOWE.exists() else "🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
#  Motyw / wygląd (inny niż liga) — wstrzyknięty CSS
# =============================================================================
TERAKOTA = "#bc5b3c"        # ceglasta terakota (kolor mączki)
TERAKOTA_CIEMNA = "#8f3f24"
GRAFIT = "#322e2a"          # ciepły grafit (nagłówki / tekst)
KREM = "#fbf6ef"            # kremowe tło
KREM_CIEPLY = "#f3ebe0"     # tło panelu bocznego
MASTERS_TLO = "#f6d7cd"     # podświetlenie kwalifikacji do Masters

st.markdown(
    f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&display=swap');

      .stApp {{ background-color: {KREM}; }}
      section[data-testid="stSidebar"] {{ background-color: {KREM_CIEPLY}; }}
      [data-testid="stHeader"] {{ background: transparent; }}

      .ct-hero {{
          background: linear-gradient(120deg, {TERAKOTA} 0%, {TERAKOTA_CIEMNA} 100%);
          color: #fff; border-radius: 18px; padding: 22px 28px; margin-bottom: 10px;
          box-shadow: 0 8px 24px rgba(143,63,36,.28);
      }}
      .ct-hero h1 {{
          font-family: 'Montserrat', sans-serif; font-weight: 800;
          font-size: 1.7rem; margin: 0; letter-spacing: .3px;
      }}
      .ct-hero p {{ margin: .35rem 0 0; opacity: .92; font-size: .95rem; }}
      .ct-badge {{
          display:inline-block; background:{GRAFIT}; color:#fff; font-weight:700;
          padding:2px 12px; border-radius:999px; font-size:.8rem; margin-top:8px;
      }}

      /* Zakładki jako „pigułki" */
      div[data-baseweb="tab-list"] {{ gap: 6px; flex-wrap: wrap; }}
      button[data-baseweb="tab"] {{
          background: #efe4d6; border-radius: 10px 10px 0 0; padding: 6px 14px;
          font-family:'Montserrat',sans-serif; font-weight:600; color:{GRAFIT};
      }}
      button[data-baseweb="tab"][aria-selected="true"] {{
          background: {TERAKOTA}; color: #fff;
      }}
      button[data-baseweb="tab"][aria-selected="true"] p {{ color:#fff; }}

      h2, h3 {{ font-family:'Montserrat',sans-serif; color:{GRAFIT}; }}

      .ct-data {{ font-family:'Montserrat',sans-serif; font-weight:700;
                  color:{TERAKOTA_CIEMNA}; font-size:1.05rem; }}
      div[data-testid="stVerticalBlockBorderWrapper"] {{
          border-radius: 14px; background: #fffdfa;
      }}
      .stButton button[kind="primary"],
      .stFormSubmitButton button[kind="primaryFormSubmit"] {{
          background:{TERAKOTA}; border-color:{TERAKOTA}; color:#fff;
      }}
      .stButton button[kind="primary"]:hover,
      .stFormSubmitButton button[kind="primaryFormSubmit"]:hover {{
          background:{TERAKOTA_CIEMNA}; border-color:{TERAKOTA_CIEMNA};
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
#  Pomocnicze
# =============================================================================
def _admin() -> bool:
    return bool(st.session_state.get("cykl_admin"))


def _etykieta_turnieju(t: dict) -> str:
    ikona = "🏆" if t["masters"] else "🎾"
    return f"{ikona} {t['data']}"


def _wynik_txt(m: dict) -> str:
    res = cykl_logic.wynik_gemowy(m)
    if res is None:
        return "—"
    return f"{res[0]}:{res[1]}"


def _int_lub_na(v):
    try:
        if v is None or str(v).strip() == "":
            return pd.NA
        return int(float(v))
    except (TypeError, ValueError):
        return pd.NA


def _blank_none(x):
    """Pusty / biały napis -> None (listy rozwijane traktują None jako brak wartości)."""
    s = "" if x is None else str(x).strip()
    return s or None


def _gem_zapis(v):
    """Wartość z listy gemów -> int, albo '' gdy puste/niepoprawne."""
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    try:
        return int(float(s))
    except ValueError:
        return ""


# =============================================================================
#  Nagłówek + logowanie
# =============================================================================
def naglowek() -> None:
    kol_logo, kol_tekst = st.columns([1, 6], vertical_alignment="center")
    if LOGO_PIONOWE.exists():
        kol_logo.image(str(LOGO_PIONOWE), width=92)
    kol_tekst.markdown(
        """
        <div class="ct-hero">
          <h1>Cykl Turniejów Singlowych</h1>
          <p>NP Tennis Academy · sezon 2026/2027 · 6 turniejów + finał Masters</p>
          <span class="ct-badge">Każdy z każdym w grupach · klasyfikacja generalna K / M</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panel_logowania() -> None:
    with st.sidebar:
        st.markdown("### 🔒 Administrator")
        if _admin():
            st.success("Zalogowano jako administrator.")
            if st.button("Wyloguj"):
                st.session_state["cykl_admin"] = False
                st.rerun()
        else:
            haslo = store.haslo_admina()
            with st.form("cykl_login"):
                podane = st.text_input("Hasło administratora", type="password")
                if st.form_submit_button("Zaloguj"):
                    if haslo and podane == haslo:
                        st.session_state["cykl_admin"] = True
                        st.rerun()
                    elif not haslo:
                        st.error("Brak ustawionego hasła admina (sekcja [admin] w secrets).")
                    else:
                        st.error("Błędne hasło.")
            st.caption("Widok publiczny jest tylko do odczytu.")
        st.markdown("---")
        if _admin():
            st.caption(f"Tryb danych: **{store.tryb()}**")
        st.caption("Cykl Turniejów • NP Tennis Academy")


# =============================================================================
#  Widok: pojedynczy turniej
# =============================================================================
def widok_turnieju(t: dict) -> None:
    st.markdown(f"<div class='ct-data'>📅 {t['data']} — {t['nazwa']}</div>",
                unsafe_allow_html=True)
    if t["masters"]:
        st.info("🏆 **Turniej Masters (finał)** — grają zakwalifikowani z klasyfikacji "
                "generalnej (8 K + 8 M). Format ustalają organizatorzy; składy i rozpiska "
                "pojawią się tutaj po losowaniu.")

    tab_k, tab_m = st.tabs([f"👩 {C.PLCIE['K']}", f"👨 {C.PLCIE['M']}"])
    with tab_k:
        widok_plci(t["id"], "K")
    with tab_m:
        widok_plci(t["id"], "M")


def widok_plci(turniej_id: str, plec: str) -> None:
    grupy = store.nazwy_grup(turniej_id, plec)

    if not grupy and not _admin():
        st.info("Składy pojawią się po losowaniu przez organizatorów.")
        return

    for grupa in grupy:
        _karta_grupy(turniej_id, plec, grupa)

    if _admin():
        _karta_nowa_grupa(turniej_id, plec, grupy)


def _karta_grupy(turniej_id: str, plec: str, grupa: str) -> None:
    zawodnicy = store.zawodnicy_grupy(turniej_id, plec, grupa)
    mecze = cykl_logic.uporzadkuj_mecze(zawodnicy, store.mecze_grupy(turniej_id, plec, grupa))

    with st.container(border=True):
        if _admin():
            c_tyt, c_del = st.columns([6, 1], vertical_alignment="center")
            c_tyt.markdown(f"### 🎾 Grupa {grupa}")
            if c_del.button("🗑️", key=f"del_{turniej_id}_{plec}_{grupa}",
                            help="Usuń grupę"):
                try:
                    store.usun_grupe(turniej_id, plec, grupa)
                    st.toast(f"Usunięto grupę {grupa}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Błąd: {e}")
        else:
            st.markdown(f"### 🎾 Grupa {grupa}")

        kol_tabela, kol_rozpiska = st.columns([2, 3])

        with kol_tabela:
            st.markdown("**Tabela grupy**")
            if _admin():
                _roster_admin(turniej_id, plec, grupa, zawodnicy)
            _tabela_grupy(zawodnicy, mecze)

        with kol_rozpiska:
            st.markdown("**Rozpiska meczów**")
            if _admin():
                if mecze:
                    st.caption("Rozpiska wygenerowana automatycznie — edytuj korty, "
                               "godziny i wyniki poniżej.")
                    _edytor_rozpiski(mecze, klucz=f"{turniej_id}_{plec}_{grupa}")
                else:
                    st.caption("Wpisz nazwiska w tabeli grupy obok — rozpiska meczów "
                               "wygeneruje się sama.")
            else:
                _rozpiska_publiczna(mecze)


def _rozpiska_publiczna(mecze: list[dict]) -> None:
    if not mecze:
        st.caption("Brak meczów.")
        return
    wiersze = [{
        "Mecz": f"{m.get('ZawodnikA','')} – {m.get('ZawodnikB','')}",
        "Kort": m.get("Kort", "") or "—",
        "Godzina": m.get("Godzina", "") or "—",
        "Wynik": _wynik_txt(m),
    } for m in mecze]
    df = pd.DataFrame(wiersze)
    df.index = [""] * len(df)
    st.table(df)


def _edytor_rozpiski(mecze: list[dict], klucz: str) -> None:
    if not mecze:
        st.caption("Brak meczów (dodaj skład grupy poniżej).")
        return
    def _gem_str(v):
        iv = _int_lub_na(v)
        return None if pd.isna(iv) else str(int(iv))

    df = pd.DataFrame([{
        "ID": m.get("ID", ""),
        "Mecz": f"{m.get('ZawodnikA','')} – {m.get('ZawodnikB','')}",
        "Kort": _blank_none(m.get("Kort")),
        "Godzina": _blank_none(m.get("Godzina")),
        "GemyA": _gem_str(m.get("GemyA")),
        "GemyB": _gem_str(m.get("GemyB")),
    } for m in mecze])

    # Opcje list rozwijanych; dołączamy ewentualne nietypowe wartości już zapisane,
    # żeby edytor nie oznaczył ich jako błędne.
    kort_opcje = list(C.KORTY)
    godz_opcje = list(C.GODZINY)
    for m in mecze:
        k = str(m.get("Kort", "")).strip()
        if k and k not in kort_opcje:
            kort_opcje.append(k)
        g = str(m.get("Godzina", "")).strip()
        if g and g not in godz_opcje:
            godz_opcje.append(g)

    edited = st.data_editor(
        df, key=f"ed_{klucz}", hide_index=True, width="stretch",
        column_order=["Mecz", "Kort", "Godzina", "GemyA", "GemyB"],
        column_config={
            "Mecz": st.column_config.TextColumn("Mecz", disabled=True),
            "Kort": st.column_config.SelectboxColumn("Kort", options=kort_opcje,
                                                     required=False),
            "Godzina": st.column_config.SelectboxColumn("Godzina", options=godz_opcje,
                                                        required=False),
            "GemyA": st.column_config.SelectboxColumn("Gemy ◀", options=C.GEMY_OPCJE,
                                                      required=False,
                                                      help="Gemy pierwszego zawodnika"),
            "GemyB": st.column_config.SelectboxColumn("Gemy ▶", options=C.GEMY_OPCJE,
                                                      required=False,
                                                      help="Gemy drugiego zawodnika"),
        },
    )
    if st.button("💾 Zapisz rozpiskę i wyniki", key=f"save_{klucz}", type="primary"):
        try:
            for _, r in edited.iterrows():
                store.aktualizuj_mecz(str(r["ID"]), {
                    "Kort": "" if pd.isna(r["Kort"]) else str(r["Kort"]).strip(),
                    "Godzina": "" if pd.isna(r["Godzina"]) else str(r["Godzina"]).strip(),
                    "GemyA": _gem_zapis(r["GemyA"]),
                    "GemyB": _gem_zapis(r["GemyB"]),
                })
            st.toast("Zapisano rozpiskę i wyniki.")
            st.rerun()
        except Exception as e:
            st.error(f"Błąd zapisu: {e}")


def _tabela_grupy(zawodnicy: list[str], mecze: list[dict]) -> None:
    if not zawodnicy:
        st.caption("Brak składu grupy.")
        return
    tabela = cykl_logic.standings_grupy(zawodnicy, mecze)
    komplet = all(w["Miejsce"] is not None for w in tabela) and tabela
    wiersze = [{
        "Poz.": (w["Miejsce"] if w["Miejsce"] is not None else "–"),
        "Zawodnik": w["Zawodnik"],
        "M": w["Mecze"],
        "W": w["Wygrane"],
        "+/- gemów": f"{w['Różnica gemów']:+d}",
        "Pkt": w["Punkty"] if komplet else "–",
    } for w in tabela]
    df = pd.DataFrame(wiersze)
    df.index = [""] * len(df)
    st.table(df)
    if not komplet:
        st.caption("⏳ Tabela na żywo — punkty do generalnej naliczą się po rozegraniu "
                   "wszystkich meczów grupy.")


# =============================================================================
#  Panel admina: składy grup
# =============================================================================
def _roster_admin(turniej_id: str, plec: str, grupa: str,
                  zawodnicy: list[str]) -> None:
    """Edycja nazwisk wprost w tabeli grupy — zapis regeneruje rozpiskę meczów."""
    with st.form(f"roster_{turniej_id}_{plec}_{grupa}"):
        st.caption("Wpisz nazwiska (do 4). Rozpiska i tabela uzupełnią się same; "
                   "wyniki rozegranych par zostają zachowane.")
        biez = (zawodnicy + [""] * C.ROZMIAR_GRUPY)[:C.ROZMIAR_GRUPY]
        osoby = [st.text_input(f"Zawodnik {i+1}", value=biez[i],
                               key=f"rn_{turniej_id}_{plec}_{grupa}_{i}")
                 for i in range(C.ROZMIAR_GRUPY)]
        zapisz = st.form_submit_button("💾 Zapisz nazwiska", type="primary")
    if zapisz:
        _zapisz_sklad(turniej_id, plec, grupa, osoby)


def _karta_nowa_grupa(turniej_id: str, plec: str, istniejace: list[str]) -> None:
    with st.container(border=True):
        st.markdown("### ➕ Nowa grupa")
        with st.form(f"new_{turniej_id}_{plec}"):
            nazwa = st.text_input("Nazwa grupy", value=_nastepna_litera(istniejace),
                                  max_chars=12)
            st.caption("Wpisz nazwiska (do 4) — rozpiska wygeneruje się automatycznie.")
            c = st.columns(C.ROZMIAR_GRUPY)
            osoby = [c[i].text_input(f"Zawodnik {i+1}", key=f"ng_{turniej_id}_{plec}_{i}")
                     for i in range(C.ROZMIAR_GRUPY)]
            if st.form_submit_button("Utwórz grupę", type="primary"):
                _zapisz_sklad(turniej_id, plec, nazwa.strip(), osoby, nowa=True)


def _zapisz_sklad(turniej_id: str, plec: str, grupa: str,
                  osoby: list[str], nowa: bool = False) -> None:
    osoby_cz = [o.strip() for o in osoby if o.strip()]
    if nowa and not grupa:
        st.error("Podaj nazwę grupy.")
        return
    if len(osoby_cz) < 2:
        st.error("Grupa potrzebuje co najmniej 2 zawodników.")
        return
    if len(set(osoby_cz)) != len(osoby_cz):
        st.error("Zawodnicy w grupie muszą być różni.")
        return
    try:
        store.zapisz_grupe(turniej_id, plec, grupa, osoby_cz)
        st.toast(f"Zapisano grupę {grupa}.")
        st.rerun()
    except Exception as e:
        st.error(f"Błąd zapisu: {e}")


def _nastepna_litera(istniejace: list[str]) -> str:
    uzyte = {s.strip().upper() for s in istniejace}
    for kod in range(ord("A"), ord("Z") + 1):
        if chr(kod) not in uzyte:
            return chr(kod)
    return ""


# =============================================================================
#  Widok: klasyfikacja generalna
# =============================================================================
def widok_generalnej() -> None:
    st.markdown("<div class='ct-data'>🏆 Klasyfikacja generalna</div>",
                unsafe_allow_html=True)
    st.caption(f"Na czerwono — pierwszych {C.LIMIT_MASTERS} zawodników w każdej kategorii, "
               "którzy na ten moment kwalifikują się do turnieju Masters.")

    grupy = store.pobierz_grupy()
    mecze = store.pobierz_mecze()

    tab_k, tab_m = st.tabs([f"👩 {C.PLCIE['K']}", f"👨 {C.PLCIE['M']}"])
    with tab_k:
        _tabela_generalna(grupy, mecze, "K")
    with tab_m:
        _tabela_generalna(grupy, mecze, "M")


def _tabela_generalna(grupy: list[dict], mecze: list[dict], plec: str) -> None:
    df = cykl_logic.klasyfikacja_generalna(grupy, mecze, plec)
    if df.empty:
        st.info("Brak danych — klasyfikacja pojawi się po pierwszych rozegranych grupach.")
        return

    df = df.copy()
    df.insert(0, "Poz.", range(1, len(df) + 1))
    df["Masters"] = ["🔴" if i < C.LIMIT_MASTERS else "" for i in range(len(df))]

    limit = C.LIMIT_MASTERS

    def podswietl(row):
        kwalifikuje = row["Poz."] <= limit
        tlo = f"background-color: {MASTERS_TLO}; font-weight: 700;" if kwalifikuje else ""
        return [tlo] * len(row)

    styler = (df.style
              .apply(podswietl, axis=1)
              .hide(axis="index"))
    st.dataframe(styler, width="stretch", hide_index=True,
                 column_config={
                     "Poz.": st.column_config.NumberColumn(width="small"),
                     "Punkty": st.column_config.NumberColumn("Punkty"),
                     "Pkt za miejsca": st.column_config.NumberColumn("Pkt za miejsca"),
                     "Bonusy": st.column_config.NumberColumn("Bonusy (+2 do zera)"),
                     "Turnieje": st.column_config.NumberColumn("Turnieje"),
                 })
    if len(df) > limit:
        prog = df.iloc[limit - 1]["Punkty"]
        st.caption(f"Próg kwalifikacji (miejsce {limit}.): **{prog} pkt**.")


# =============================================================================
#  Widok: strona główna
# =============================================================================
def _kafelek(ikona: str, tytul: str, opis: str) -> None:
    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:1.7rem;line-height:1'>{ikona}</div>"
            f"<div style='font-family:Montserrat,sans-serif;font-weight:700;"
            f"color:{GRAFIT};margin-top:4px'>{tytul}</div>"
            f"<div style='color:#6b625a;font-size:.9rem;margin-top:2px'>{opis}</div>",
            unsafe_allow_html=True,
        )


def widok_glowna() -> None:
    st.markdown("## Witamy w Cyklu Turniejów Singlowych! 🎾")
    st.markdown(
        """
        Cieszymy się, że tu jesteś! **Cykl Turniejów Singlowych NP Tennis Academy**
        to seria **6 turniejów** zwieńczona wielkim finałem **Masters** — rozgrywki
        dla każdego, kto kocha tenisa i zdrową, sportową rywalizację.

        Grasz w **4-osobowych grupach systemem każdy z każdym**, zdobywasz punkty do
        **klasyfikacji generalnej** (osobno kobiety i mężczyźni), a **8 najlepszych**
        osób w każdej kategorii walczy o tytuł w turnieju Masters. Najważniejsze są
        gra fair, dobra atmosfera i rywalizacja z uśmiechem! 💪
        """
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        _kafelek("🗓️", "6 turniejów + Masters", "Od 22.11.2026 do finału 16.05.2027.")
    with c2:
        _kafelek("👥", "Grupy 4-osobowe", "Każdy z każdym · mecz 40 min z rozgrzewką.")
    with c3:
        _kafelek("🏆", "Najlepsza 8 → Masters", "Czołówka klasyfikacji K i M gra w finale.")

    st.markdown("### 📝 Jak dołączyć?")
    st.markdown(
        """
        - Zapisy prowadzimy **osobno na każdy turniej** przez system **Luppo** —
          link do zapisów przekazują organizatorzy.
        - Zgłaszasz się indywidualnie; grupy losujemy po zamknięciu zapisów, a
          rozpiskę meczów publikujemy najpóźniej w przeddzień turnieju.
        - Pełne zasady znajdziesz w zakładce **📜 Regulamin**.
        """
    )
    st.success("Gotowy na rywalizację? Zapisz się na najbliższy turniej i do zobaczenia "
               "na korcie! 🎾")
    st.caption("Masz pytania? Organizatorzy: Tomasz Turek · Marcel Jaskuła "
               "(kontakt w zakładce Regulamin).")


# =============================================================================
#  Widok: regulamin
# =============================================================================
def widok_regulamin() -> None:
    st.markdown("<div class='ct-data'>📜 Regulamin cyklu</div>", unsafe_allow_html=True)
    plik = BASE_DIR / "data" / "regulamin_cykl.md"
    if plik.exists():
        st.markdown(plik.read_text(encoding="utf-8"))
    else:
        st.info("Treść regulaminu znajdziesz w pliku `data/regulamin_cykl.md`.")


# =============================================================================
#  Główne
# =============================================================================
def main() -> None:
    panel_logowania()
    naglowek()

    etykiety = (["🏠 Start", "📜 Regulamin"]
                + [_etykieta_turnieju(t) for t in C.TURNIEJE]
                + ["🏆 Klasyfikacja generalna"])
    zakladki = st.tabs(etykiety)

    with zakladki[0]:
        widok_glowna()

    with zakladki[1]:
        widok_regulamin()

    for i, t in enumerate(C.TURNIEJE):
        with zakladki[i + 2]:
            try:
                widok_turnieju(t)
            except Exception as e:
                st.error("Nie udało się wczytać danych turnieju.")
                with st.expander("Szczegóły (dla organizatora)"):
                    st.exception(e)

    with zakladki[-1]:
        try:
            widok_generalnej()
        except Exception as e:
            st.error("Nie udało się wczytać klasyfikacji.")
            with st.expander("Szczegóły (dla organizatora)"):
                st.exception(e)

    st.markdown("---")
    st.caption("© 2026/2027 Cykl Turniejów Singlowych · NP Tennis Academy · "
               "aplikację stworzył **Tomek Turek** 🎾")


main()
