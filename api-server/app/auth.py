"""JWT authentication module.

Users stored in SQLite, passwords hashed with SHA-256.
Default admin: admin / admin123
JWT tokens: access_token (2h), refresh_token (7d)
"""

import sqlite3
import os
import hashlib
import json
from datetime import datetime, timezone, timedelta
import jwt

AUTH_DB = os.environ.get('AUTH_DB', '/app/data/auth.db')
JWT_SECRET = os.environ.get('JWT_SECRET', 'aiops-jwt-secret-change-me')
ACCESS_TOKEN_EXP = 7200       # 2 hours
REFRESH_TOKEN_EXP = 604800    # 7 days


def _get_conn():
    os.makedirs(os.path.dirname(AUTH_DB), exist_ok=True)
    conn = sqlite3.connect(AUTH_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_auth_db():
    conn = _get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'operator',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')
    # Create default admin if not exists
    existing = conn.execute('SELECT id FROM users WHERE username = ?', ('admin',)).fetchone()
    if not existing:
        pw_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
            ('admin', pw_hash, 'admin', now)
        )
        print('Default admin user created (admin / admin123)')
    conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(username: str, password: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        'SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?',
        (username, _hash_password(password))
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        'user_id': row['id'],
        'username': row['username'],
        'role': row['role']
    }


def create_tokens(user: dict) -> dict:
    init_auth_db()  # lazy init
    now = datetime.now(timezone.utc)

    access_payload = {
        'sub': str(user['user_id']),
        'username': user['username'],
        'role': user['role'],
        'exp': now + timedelta(seconds=ACCESS_TOKEN_EXP),
        'iat': now,
        'type': 'access'
    }
    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm='HS256')

    refresh_payload = {
        'sub': str(user['user_id']),
        'exp': now + timedelta(seconds=REFRESH_TOKEN_EXP),
        'iat': now,
        'type': 'refresh'
    }
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm='HS256')

    # Store refresh token in DB
    conn = _get_conn()
    expires = (now + timedelta(seconds=REFRESH_TOKEN_EXP)).isoformat()
    conn.execute(
        'INSERT INTO refresh_tokens (token, user_id, expires_at) VALUES (?, ?, ?)',
        (refresh_token, user['user_id'], expires)
    )
    conn.commit()
    conn.close()

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer',
        'expires_in': ACCESS_TOKEN_EXP,
        'user': {
            'id': user['user_id'],
            'username': user['username'],
            'role': user['role']
        }
    }


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def refresh_access(refresh_token: str) -> dict | None:
    # Verify the token is in our DB and not revoked
    conn = _get_conn()
    row = conn.execute(
        'SELECT user_id FROM refresh_tokens WHERE token = ?',
        (refresh_token,)
    ).fetchone()
    if not row:
        conn.close()
        return None

    payload = verify_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        conn.close()
        return None

    user_id = payload['sub']
    user_row = conn.execute(
        'SELECT id, username, role FROM users WHERE id = ?',
        (int(user_id),)
    ).fetchone()
    conn.close()

    if not user_row:
        return None

    return create_tokens({
        'user_id': user_row['id'],
        'username': user_row['username'],
        'role': user_row['role']
    })


def revoke_token(refresh_token: str):
    conn = _get_conn()
    conn.execute('DELETE FROM refresh_tokens WHERE token = ?', (refresh_token,))
    conn.commit()
    conn.close()


def list_users():
    conn = _get_conn()
    rows = conn.execute(
        'SELECT id, username, role, created_at FROM users ORDER BY id'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(username: str, password: str, role: str = 'operator'):
    conn = _get_conn()
    pw_hash = _hash_password(password)
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
            (username, pw_hash, role, now)
        )
        conn.commit()
        return {'id': conn.execute('SELECT last_insert_rowid()').fetchone()[0], 'username': username, 'role': role}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0
