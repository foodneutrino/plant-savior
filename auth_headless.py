"""Google OAuth2 authentication for headless devices (e.g. Raspberry Pi).

Instead of opening a browser, this script prints an authorization URL.
Visit the URL on any device, grant access, and paste the authorization code back.

Run this script once to generate token.json:
    python auth_headless.py

Prerequisites:
    1. Create a project in Google Cloud Console
    2. Enable the Google Calendar API
    3. Create OAuth2 credentials (Desktop application)
    4. Download the credentials JSON and save as credentials.json in this directory
"""

import json
from pathlib import Path
from urllib.parse import urlencode

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_PATH = Path(__file__).parent / "token.json"
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _load_client_config() -> dict | None:
    """Load client_id and client_secret from credentials.json."""
    if not CREDENTIALS_PATH.exists():
        print(f"ERROR: {CREDENTIALS_PATH} not found.")
        print("Download OAuth2 credentials from Google Cloud Console and save here.")
        return None

    data = json.loads(CREDENTIALS_PATH.read_text())
    # credentials.json nests under "installed" or "web"
    key = "installed" if "installed" in data else "web"
    return data[key]


def get_credentials() -> Credentials | None:
    """Load existing credentials or run the headless OAuth2 flow.

    Returns valid credentials, or None if credentials.json is missing.
    """
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
        return creds

    client_config = _load_client_config()
    if client_config is None:
        return None

    client_id = client_config["client_id"]
    client_secret = client_config["client_secret"]
    redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    # Build the authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    print("Visit the following URL on any device to authorize this app:\n")
    print(auth_url)
    print()
    code = input("Paste the authorization code here: ").strip()

    # Exchange the authorization code for tokens
    token_response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )

    if token_response.status_code != 200:
        print(f"ERROR: Token exchange failed: {token_response.text}")
        return None

    token_data = token_response.json()

    # Build a Credentials object and save it
    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    TOKEN_PATH.write_text(creds.to_json())
    print("Authentication successful. Token saved to token.json")
    return creds


if __name__ == "__main__":
    creds = get_credentials()
    if creds:
        print("Credentials are valid.")
    else:
        print("Failed to obtain credentials.")
