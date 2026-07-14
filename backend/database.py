"""Minimal SQLite user store. Only accounts are persisted — MoM media stays ephemeral."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "meetingly.db"

_lock = threading.Lock()


@dataclass
class User:
    id: int
    email: str
    name: str
    password_hash: str
    created_at: str


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def create_user(*, email: str, name: str, password_hash: str) -> User:
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO users (email, name, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (email.strip().lower(), name.strip(), password_hash, now),
            )
            conn.commit()
            user_id = int(cur.lastrowid)
            return User(
                id=user_id,
                email=email.strip().lower(),
                name=name.strip(),
                password_hash=password_hash,
                created_at=now,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Email already registered") from exc
        finally:
            conn.close()


def get_user_by_email(email: str) -> User | None:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id, email, name, password_hash, created_at FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
            if not row:
                return None
            return User(**dict(row))
        finally:
            conn.close()


def get_user_by_id(user_id: int) -> User | None:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id, email, name, password_hash, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return User(**dict(row))
        finally:
            conn.close()
