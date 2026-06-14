"""
Generuje .streamlit/secrets.toml z pobranego pliku JSON konta serwisowego.

Użycie:
    python make_secrets.py "C:\\Users\\tomas\\Downloads\\nazwa-klucza.json"

Skrypt zapyta o ID arkusza (możesz wkleić cały link – ID wyciągnie sam)
oraz o hasło administratora, a potem zapisze gotowy plik secrets.toml.
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).parent
WYJSCIE = BASE / ".streamlit" / "secrets.toml"

POLA = [
    "type", "project_id", "private_key_id", "private_key", "client_email",
    "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url",
    "client_x509_cert_url", "universe_domain",
]


def toml_wartosc(v: str) -> str:
    # JSON i TOML używają tych samych sekwencji (\n, \", \\), więc json.dumps
    # daje poprawny, bezpieczny napis dla TOML – także dla wieloliniowego private_key.
    return json.dumps("" if v is None else str(v), ensure_ascii=False)


def wyciagnij_id(tekst: str) -> str:
    tekst = tekst.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", tekst)
    return m.group(1) if m else tekst


def main():
    if len(sys.argv) < 2:
        sys.exit('Podaj ścieżkę do pliku JSON, np.:\n  python make_secrets.py "C:\\Users\\tomas\\Downloads\\klucz.json"')

    sciezka_json = Path(sys.argv[1].strip('"'))
    if not sciezka_json.exists():
        sys.exit(f"Nie znaleziono pliku: {sciezka_json}")

    with open(sciezka_json, encoding="utf-8") as f:
        dane = json.load(f)

    if dane.get("type") != "service_account":
        print("[!] Uwaga: to nie wyglada na klucz konta uslugi (brak type=service_account).")

    arkusz = wyciagnij_id(input("Wklej ID arkusza lub cały jego link: "))
    haslo = input("Ustaw hasło administratora (panel akceptacji): ").strip()

    linie = [
        "[google_sheets]",
        f"spreadsheet_id = {toml_wartosc(arkusz)}",
        "",
        "[admin]",
        f"password = {toml_wartosc(haslo)}",
        "",
        "[gcp_service_account]",
    ]
    for pole in POLA:
        if pole in dane:
            linie.append(f"{pole} = {toml_wartosc(dane[pole])}")

    WYJSCIE.parent.mkdir(exist_ok=True)
    WYJSCIE.write_text("\n".join(linie) + "\n", encoding="utf-8")

    print(f"\n[OK] Zapisano: {WYJSCIE}")
    print(f"  Konto serwisowe: {dane.get('client_email','?')}")
    print("\nNastepne kroki:")
    print("  1. Udostepnij arkusz temu adresowi (jako Edytor):")
    print(f"     {dane.get('client_email','?')}")
    print("  2. python seed_sheets.py")
    print("  3. streamlit run app.py")


if __name__ == "__main__":
    main()
