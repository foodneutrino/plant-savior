"""Google OAuth2 authentication for Calendar API access.

Run this script once to generate token.json:
    python auth.py

Prerequisites:
    1. Create a project in Google Cloud Console
    2. Enable the Google Calendar API
    3. Create OAuth2 credentials (Desktop application)
    4. Download the credentials JSON and save as credentials.json in this directory
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_PATH = Path(__file__).parent / "token.json"
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"


def get_credentials() -> Credentials | None:
    """Load existing credentials or run the OAuth2 flow.

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

    if not CREDENTIALS_PATH.exists():
        print(f"ERROR: {CREDENTIALS_PATH} not found.")
        print("Download OAuth2 credentials from Google Cloud Console and save here.")
        return None

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=8090)
    TOKEN_PATH.write_text(creds.to_json())
    print("Authentication successful. Token saved to token.json")
    return creds


if __name__ == "__main__":
    creds = get_credentials()
    if creds:
        print("Credentials are valid.")
    else:
        print("Failed to obtain credentials.")
