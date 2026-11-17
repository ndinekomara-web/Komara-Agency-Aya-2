"""
Stockage local des conversations (SQLite).

Une « session » remplace ici le chat Telegram : c'est un identifiant créé par
le navigateur et conservé sur l'appareil. Les messages y sont enregistrés pour
que l'historique survive à un rechargement de page ou à un redémarrage du
serveur.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any

from config import MEMORY_DIR, SQLITE_DB_PATH

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    connection = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with _lock, _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                lang TEXT,
                created_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                lang TEXT,
                created_at REAL NOT NULL,
                last_seen REAL NOT NULL
            )
            """
        )


def touch_session(session_id: str, lang: str | None = None) -> None:
    now = time.time()
    with _lock, _connect() as connection:
        row = connection.execute(
            "SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            if lang:
                connection.execute(
                    "UPDATE sessions SET last_seen = ?, lang = ? WHERE session_id = ?",
                    (now, lang, session_id),
                )
            else:
                connection.execute(
                    "UPDATE sessions SET last_seen = ? WHERE session_id = ?",
                    (now, session_id),
                )
        else:
            connection.execute(
                "INSERT INTO sessions (session_id, lang, created_at, last_seen) VALUES (?, ?, ?, ?)",
                (session_id, lang, now, now),
            )


def add_message(session_id: str, role: str, content: str, lang: str | None = None) -> None:
    with _lock, _connect() as connection:
        connection.execute(
            "INSERT INTO messages (session_id, role, content, lang, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, lang, time.time()),
        )


def history(session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    with _lock, _connect() as connection:
        rows = connection.execute(
            "SELECT role, content, lang, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def clear(session_id: str) -> int:
    with _lock, _connect() as connection:
        cursor = connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        return cursor.rowcount


def stats() -> dict[str, int]:
    with _lock, _connect() as connection:
        sessions = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        messages = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    return {"sessions": sessions, "messages": messages}
