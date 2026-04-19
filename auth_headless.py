"""Google OAuth2 authentication for headless devices (e.g. Raspberry Pi).

Uses the OAuth 2.0 Device Authorization Flow (RFC 8628): the device
requests a short ``user_code`` from Google, the user enters it at a
verification URL on any browser-capable device, and we poll the token
endpoint until the user completes consent.

Prerequisites:
    1. Create a project in Google Cloud Console.
    2. Enable the Google Calendar API.
    3. Create OAuth2 credentials of type **TVs and Limited Input devices**
       (NOT "Desktop application" — the device flow is restricted to that
       client type).
    4. Download the credentials JSON and save as ``credentials.json`` in
       this directory.

Run once to generate ``token.json``:
    python auth_headless.py
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_PATH = Path(__file__).parent / "token.json"
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"

DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


@dataclass(frozen=True)
class _ClientConfig:
    """Minimal OAuth client configuration loaded from ``credentials.json``."""

    client_id: str
    client_secret: str


@dataclass(frozen=True)
class _DeviceCode:
    """Response from the device authorization endpoint."""

    device_code: str
    user_code: str
    verification_url: str
    expires_in: int
    interval: int


def _load_client_config() -> _ClientConfig | None:
    """Load ``client_id`` and ``client_secret`` from ``credentials.json``."""
    if not CREDENTIALS_PATH.exists():
        print(f"ERROR: {CREDENTIALS_PATH} not found.")
        print("Download OAuth2 credentials from Google Cloud Console and save here.")
        return None

    data = json.loads(CREDENTIALS_PATH.read_text())
    key = "installed" if "installed" in data else "web"
    section = data.get(key)
    if not section or "client_id" not in section or "client_secret" not in section:
        print(f"ERROR: {CREDENTIALS_PATH} is missing client_id/client_secret.")
        return None

    return _ClientConfig(
        client_id=section["client_id"],
        client_secret=section["client_secret"],
    )


def _request_device_code(config: _ClientConfig) -> _DeviceCode | None:
    """Kick off the device authorization flow with Google."""
    response = requests.post(
        DEVICE_CODE_URL,
        data={"client_id": config.client_id, "scope": " ".join(SCOPES)},
    )
    if response.status_code != 200:
        print(f"ERROR: device code request failed: {response.text}")
        return None

    payload = response.json()
    # Google returns ``verification_url`` (legacy) rather than the
    # RFC 8628 ``verification_uri`` name. Accept either.
    verification_url = payload.get("verification_url") or payload.get("verification_uri")
    return _DeviceCode(
        device_code=payload["device_code"],
        user_code=payload["user_code"],
        verification_url=verification_url,
        expires_in=int(payload["expires_in"]),
        interval=int(payload.get("interval", 5)),
    )


def _poll_for_token(config: _ClientConfig, device: _DeviceCode) -> dict | None:
    """Poll Google's token endpoint until the user completes consent.

    Implements the backoff rules from RFC 8628 §3.5:
    ``authorization_pending`` keeps the current interval, ``slow_down``
    increases it by 5 seconds, any other error aborts.
    """
    interval = device.interval
    deadline = time.monotonic() + device.expires_in

    while time.monotonic() < deadline:
        time.sleep(interval)
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "device_code": device.device_code,
                "grant_type": DEVICE_GRANT_TYPE,
            },
        )
        payload = response.json()
        if response.status_code == 200:
            return payload

        error = payload.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        print(f"ERROR: token polling failed: {payload}")
        return None

    print("ERROR: device code expired before authorization completed.")
    return None


def _persist_credentials(token_data: dict, config: _ClientConfig) -> Credentials:
    """Build a ``Credentials`` object from a token response and save it."""
    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=TOKEN_URL,
        client_id=config.client_id,
        client_secret=config.client_secret,
        scopes=SCOPES,
    )
    TOKEN_PATH.write_text(creds.to_json())
    return creds


def _refresh_existing() -> Credentials | None:
    """Return refreshed credentials if ``token.json`` is still usable.

    Returns ``None`` (rather than raising) when the stored token cannot
    be refreshed — e.g. it was issued for a different scope set — so the
    caller can fall through to a fresh device-flow exchange.
    """
    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.valid:
        return creds
    if not (creds.expired and creds.refresh_token):
        return None

    try:
        creds.refresh(Request())
    except RefreshError as exc:
        print(f"Stored token could not be refreshed ({exc}); re-authorizing.")
        return None

    TOKEN_PATH.write_text(creds.to_json())
    return creds


def get_credentials() -> Credentials | None:
    """Load existing credentials or run the device-flow OAuth2 exchange.

    Returns:
        Valid ``Credentials``, or ``None`` if ``credentials.json`` is
        missing or the user fails to complete consent before the code
        expires.
    """
    creds = _refresh_existing()
    if creds:
        return creds

    config = _load_client_config()
    if config is None:
        return None

    device = _request_device_code(config)
    if device is None:
        return None

    print("To authorize this device:")
    print(f"  1. On any browser, open: {device.verification_url}")
    print(f"  2. Enter the code: {device.user_code}")
    print(f"Waiting for authorization (expires in {device.expires_in}s)...\n")

    token_data = _poll_for_token(config, device)
    if token_data is None:
        return None

    creds = _persist_credentials(token_data, config)
    print("Authentication successful. Token saved to token.json")
    return creds


if __name__ == "__main__":
    creds = get_credentials()
    if creds:
        print("Credentials are valid.")
    else:
        print("Failed to obtain credentials.")
