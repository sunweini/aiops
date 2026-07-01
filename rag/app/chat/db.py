"""SQLite-backed conversation storage.

Schema:
  conversations(id, title, created_at, updated_at, turn_count, total_tokens)
  messages(conversation_id, role, content, sources_json, timestamp)
"""

import sqlite3
import os
import json
from datetime import datetime, timezone

DB_PATH = os.environ.get('CONVERSATIONS_DB', '/app/data/conversations.db')


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            turn_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources_json TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
    ''')
    conn.commit()
    conn.close()


def list_conversations(limit=50):
    conn = _get_conn()
    rows = conn.execute(
        'SELECT id, title, created_at, turn_count, total_tokens '
        'FROM conversations ORDER BY updated_at DESC LIMIT ?',
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {
            'conversation_id': r['id'],
            'title': r['title'],
            'created_at': r['created_at'],
            'turn_count': r['turn_count'],
            'total_tokens': r['total_tokens']
        }
        for r in rows
    ]


def create_conversation(title):
    import uuid
    conv_id = 'conv_' + uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    conn.execute(
        'INSERT INTO conversations (id, title, created_at, updated_at, turn_count, total_tokens) '
        'VALUES (?, ?, ?, ?, 0, 0)',
        (conv_id, title, now, now)
    )
    conn.commit()
    conn.close()
    return {
        'conversation_id': conv_id,
        'title': title,
        'created_at': now,
        'turn_count': 0,
        'total_tokens': 0
    }


def add_message(conv_id, role, content, sources=None):
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    conn.execute(
        'INSERT INTO messages (conversation_id, role, content, sources_json, timestamp) '
        'VALUES (?, ?, ?, ?, ?)',
        (conv_id, role, content, json.dumps(sources or []), now)
    )
    conn.execute(
        'UPDATE conversations SET updated_at = ?, turn_count = turn_count + 1 WHERE id = ?',
        (now, conv_id)
    )
    conn.commit()
    conn.close()


def update_tokens(conv_id, tokens):
    conn = _get_conn()
    conn.execute(
        'UPDATE conversations SET total_tokens = total_tokens + ? WHERE id = ?',
        (tokens, conv_id)
    )
    conn.commit()
    conn.close()

def get_conversation(conv_id):
    conn = _get_conn()
    row = conn.execute(
        'SELECT id, title, created_at, turn_count, total_tokens '
        'FROM conversations WHERE id = ?',
        (conv_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        'conversation_id': row['id'],
        'title': row['title'],
        'created_at': row['created_at'],
        'turn_count': row['turn_count'],
        'total_tokens': row['total_tokens']
    }
