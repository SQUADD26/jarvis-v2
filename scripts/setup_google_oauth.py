"""
Script per ottenere i token OAuth di Google.
Eseguire una volta per generare il refresh token.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send"
]


def main():
    print("Google OAuth Setup")
    print("=" * 50)
    print()
    print("1. Vai su https://console.cloud.google.com/")
    print("2. Crea un progetto (o usa uno esistente)")
    print("3. Abilita le API: Google Calendar, Gmail")
    print("4. Crea credenziali OAuth 2.0 (Desktop App)")
    print("5. Scarica il file JSON delle credenziali")
    print()

    creds_file = input("Percorso del file credentials.json: ").strip()

    flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
    creds = flow.run_local_server(port=8080)

    print()
    print("=" * 50)
    print("AGGIUNGI QUESTE VARIABILI AL FILE .env:")
    print("=" * 50)
    print()
    print(f"GOOGLE_CLIENT_ID={creds.client_id}")
    print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print()


if __name__ == "__main__":
    main()
