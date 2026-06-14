# 🎾 Liga Tenisowa – NP Tennis Academy



## Dwa tryby działania

| Tryb | Kiedy | Co działa |
|------|-------|-----------|
| **CSV** (domyślny) | brak konfiguracji Google | tabele i terminarze tylko do odczytu z `./data` |
| **Google Sheets** | po ustawieniu sekretów | + samodzielne zgłaszanie wyników, panel akceptacji, **tabele liczone automatycznie** z zatwierdzonych meczów |

## Uruchomienie

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Strona otworzy się pod http://localhost:8501.

## Zasady punktacji (zaszyte w aplikacji)

- Mecz do **2 wygranych setów**.
- Set zwykły: 6:0–6:4, 7:5, 7:6.
- Przy stanie **1:1** zamiast 3. seta – **super tie-break do 10** (przewaga min. 2), np. 10:7.
- Zwycięstwo = **2 pkt**, porażka = 0. O miejscu w tabeli decydują punkty, a przy równości bilans setów.

Wynik wpisuje się **z perspektywy gospodarza** (np. 6:4 = gospodarz wygrał seta).

---

## Włączenie trybu Google Sheets (samodzielne zgłaszanie + akceptacja)

### 1. Utwórz konto serwisowe w Google Cloud
1. Wejdź na https://console.cloud.google.com/ → utwórz/wybierz projekt.
2. **APIs & Services → Enable APIs** → włącz **Google Sheets API**.
3. **APIs & Services → Credentials → Create credentials → Service account**.
4. Po utworzeniu wejdź w konto → zakładka **Keys → Add key → JSON** → pobierz plik JSON.

### 2. Utwórz arkusz i udostępnij go kontu serwisowemu
1. Utwórz arkusz Google (np. „Liga Tenisowa 2026").
2. Skopiuj jego **ID** z adresu: `.../spreadsheets/d/`**`<TO_JEST_ID>`**`/edit`.
3. Kliknij **Udostępnij** i dodaj adres `client_email` z pliku JSON
   (np. `konto@projekt.iam.gserviceaccount.com`) jako **Edytor**.

### 3. Ustaw sekrety
Skopiuj `/.streamlit/secrets.toml.example` do `/.streamlit/secrets.toml`
i uzupełnij: `spreadsheet_id`, hasło administratora oraz pola `gcp_service_account`
(wartości wklejasz z pobranego pliku JSON).

> Plik `secrets.toml` jest w `.gitignore` – nie trafi do repozytorium.

### 4. Przygotuj zakładki w arkuszu
```powershell
python seed_sheets.py
```
Skrypt utworzy zakładki `mecze`, `zgloszenia`, `fairplay` z nagłówkami oraz
zaimportuje mecze i Fair Play z plików CSV (jeśli zakładki są puste).

### 5. Gotowe
Uruchom `streamlit run app.py` – w menu pojawią się **➕ Zgłoś wynik**
i **🔒 Panel akceptacji**.

## Jak to działa na co dzień

1. **Zawodnik** wybiera swój mecz, wpisuje wynik → trafia on do zakładki
   `zgloszenia` ze statusem `oczekuje`. **Tabela się nie zmienia.**
2. **Organizator** wchodzi w **Panel akceptacji** (hasło), widzi oczekujące
   zgłoszenia i klika **Akceptuj** lub **Odrzuć**.
3. Po akceptacji wynik zapisuje się w zakładce `mecze`, a tabela
   przelicza się **automatycznie**.

## Struktura arkusza

- **mecze** – rozpisane spotkania + zatwierdzone wyniki (źródło tabel).
- **zgloszenia** – dziennik zgłoszeń od zawodników (oczekuje/zaakceptowane/odrzucone).
- **fairplay** – klasyfikacja Fair Play.

## Hosting w internecie

Na **Streamlit Community Cloud** system plików jest ulotny – dlatego dane trzymamy
w Google Sheets (przetrwają restart). Sekrety wklejasz w panelu **App → Settings → Secrets**
(tę samą zawartość co `secrets.toml`).

## Pliki projektu

| Plik | Rola |
|------|------|
| `app.py` | interfejs strony |
| `liga_logic.py` | punktacja i liczenie tabeli (czysta logika) |
| `sheets.py` | połączenie z Google Sheets |
| `config.py` | lista lig i nagłówki kolumn |
| `seed_sheets.py` | jednorazowe przygotowanie arkusza |
| `test_logic.py` | testy logiki (`python test_logic.py`) |
| `data/` | dane CSV (tryb zapasowy) + `regulamin.md` |
