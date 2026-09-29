import os
import secrets
import sqlite3
from contextlib import closing

from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("TXTCLOUD_DB", os.path.join(BASE_DIR, "users.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    user_id       TEXT    NOT NULL UNIQUE,
    avatar        TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
"""


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(_connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def create_user(login, password, avatar):
    with closing(_connect()) as conn:
        for _ in range(5):
            uid = secrets.token_hex(16)
            try:
                conn.execute(
                    "INSERT INTO users (login, password_hash, user_id, avatar) "
                    "VALUES (?, ?, ?, ?)",
                    (login, generate_password_hash(password), uid, avatar),
                )
                conn.commit()
                return uid
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                if "user_id" in str(exc):
                    continue
                return None
    return None


def verify_user(login, password):
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE login = ?", (login,)
        ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return dict(row)
    return None


def get_user_by_user_id(user_id):
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None