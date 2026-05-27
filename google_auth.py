"""Shared Google OAuth2 credential manager."""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

BASE_DIR = Path(__file__).parent


def get_google_credentials(scopes: list[str]) -> Credentials | None:
    """
    Load or refresh Google OAuth2 credentials.
    Returns None if credentials.json is not present (user hasn't set up OAuth).
    Token is cached in token.json.
    """
    creds_path = BASE_DIR / "credentials.json"
    token_path = BASE_DIR / "token.json"

    if not creds_path.exists():
        return None

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds
