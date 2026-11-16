"""Read a Google Sheet with a service account.

Not a script. Set-up: create a service account, share the sheet with its email, and
save its JSON key file as ``infra/.credentials/afsmumsnet-454163761a82.json`` (gitignored).
``GOOGLE_SHEETS_CREDENTIALS`` in ``backend/.env`` overrides that path.
"""

from __future__ import annotations

import os
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CREDENTIALS = REPO_ROOT / "infra" / ".credentials" / "afsmumsnet-454163761a82.json"


def fetch_sheet(sheet_id: str, sheet_name: str) -> list[dict[str, str]]:
    """Rows of one sheet as dicts keyed by the header row.

    Args:
        sheet_id: The id in the spreadsheet's URL.
        sheet_name: The tab name.

    Returns:
        One dict per data row. Short rows are padded with empty strings.

    Raises:
        FileNotFoundError: If the key file is missing.
    """
    credentials = Credentials.from_service_account_file(
        os.environ.get("GOOGLE_SHEETS_CREDENTIALS", str(DEFAULT_CREDENTIALS)),
        scopes=SCOPES,
    )
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    rows = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=sheet_name)
        .execute()
        .get("values", [])
    )
    header, body = rows[0], rows[1:]
    return [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in body]
