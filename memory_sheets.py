"""
Journalisation des conversations vers Google Sheets — entièrement facultative.

Si les bibliothèques Google ou les identifiants ne sont pas fournis,
l'application continue de fonctionner normalement : les échanges sont alors
seulement conservés dans la base locale (``chat_store``).
"""
from __future__ import annotations

import json
import logging
import threading
import time

from config import (
    GOOGLE_CREDENTIALS_JSON,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_SHEETS_ID,
)

logger = logging.getLogger("komara.sheets")

_gc = None
_sheet = None
_lock = threading.Lock()
_disabled_reason: str | None = None


def available() -> bool:
    """Indique si le journal Sheets peut être utilisé."""
    if _disabled_reason:
        return False
    if not GOOGLE_SHEETS_ID:
        return False
    try:
        import gspread  # noqa: F401
        import oauth2client  # noqa: F401
    except Exception:
        return False
    return True


def _load_credentials(scope):
    from oauth2client.service_account import ServiceAccountCredentials

    if GOOGLE_CREDENTIALS_JSON.strip():
        return ServiceAccountCredentials.from_json_keyfile_dict(
            json.loads(GOOGLE_CREDENTIALS_JSON), scope
        )
    return ServiceAccountCredentials.from_json_keyfile_name(
        GOOGLE_CREDENTIALS_PATH, scope
    )


def _get_sheet():
    global _gc, _sheet, _disabled_reason
    if _sheet is None:
        if not available():
            _disabled_reason = _disabled_reason or "Google Sheets non configuré"
            return None
        with _lock:
            if _sheet is None:
                try:
                    import gspread

                    scope = [
                        "https://spreadsheets.google.com/feeds",
                        "https://www.googleapis.com/auth/drive",
                    ]
                    _gc = gspread.authorize(_load_credentials(scope))
                    _sheet = _gc.open_by_key(GOOGLE_SHEETS_ID).sheet1
                except Exception as exc:  # pragma: no cover - dépend du réseau
                    _disabled_reason = str(exc)
                    logger.warning("Google Sheets indisponible : %s", exc)
                    return None
    return _sheet


def _write_to_sheet(session_id, user_name, role, message, lang):
    try:
        sheet = _get_sheet()
        if sheet is None:
            return
        sheet.append_row(
            [time.strftime("%Y-%m-%d %H:%M:%S"), str(session_id), user_name, role, message, lang]
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Écriture Sheets impossible : %s", exc)


def log_conversation(session_id, user_name, role, message, lang="fr"):
    """Enregistre un échange sans bloquer la réponse."""
    if not available():
        return
    threading.Thread(
        target=_write_to_sheet,
        args=(session_id, user_name, role, message, lang),
        daemon=True,
    ).start()


def get_last_messages(session_id, n: int = 5) -> list[dict]:
    try:
        sheet = _get_sheet()
        if sheet is None:
            return []
        records = sheet.get_all_records()
        rows = [r for r in records if str(r.get("chat_id", "")) == str(session_id)]
        return rows[-n:]
    except Exception:
        return []


def diagnose() -> str:
    if not GOOGLE_SHEETS_ID:
        return "Sheets non configuré (journal local uniquement)"
    sheet = _get_sheet()
    if sheet is None:
        return f"Sheets ERREUR : {_disabled_reason}"
    return f"Sheets OK (onglet '{sheet.title}')"
