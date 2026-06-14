"""
Diagnostyka logowania do Google – czyta lokalny .streamlit/secrets.toml,
pokazuje KTÓRY klucz jest używany i próbuje pobrać token.

Uruchom:  python diag_auth.py

Nie wypisuje prywatnego klucza – tylko bezpieczne identyfikatory.
"""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request

SECRETS = Path(__file__).parent / ".streamlit" / "secrets.toml"


def main():
    if not SECRETS.exists():
        raise SystemExit(f"Brak pliku {SECRETS}")

    with open(SECRETS, "rb") as f:
        sek = tomllib.load(f)

    sa = sek.get("gcp_service_account", {})
    pk = sa.get("private_key", "")

    print("=== Co jest w secrets.toml ===")
    print(" project_id     :", sa.get("project_id"))
    print(" client_email   :", sa.get("client_email"))
    print(" private_key_id :", sa.get("private_key_id"))
    print(" spreadsheet_id :", sek.get("google_sheets", {}).get("spreadsheet_id"))
    print(" private_key zaczyna sie od:", repr(pk[:32]))
    print(" private_key konczy sie na :", repr(pk[-32:]))
    print(" liczba prawdziwych nowych linii w kluczu:", pk.count("\n"))
    print()

    try:
        creds = Credentials.from_service_account_info(
            sa, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        print("[1] Klucz PEM zaladowal sie poprawnie.")
    except Exception as e:
        print("[1] BLAD ladowania klucza:", type(e).__name__, e)
        return

    try:
        creds.refresh(Request())
        print("[2] TOKEN POBRANY POMYSLNIE -> klucz dziala. Auth jest OK.")
    except Exception as e:
        print("[2] BLAD pobierania tokenu:", str(e))


if __name__ == "__main__":
    main()
