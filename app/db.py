"""SQLite 存储层：账号、运行记录、设置。"""

import json
import os
import sqlite3
import threading
from datetime import datetime

from .config import DATA_DIR, DEFAULT_SETTINGS

DB_PATH = os.path.join(DATA_DIR, 'mcloud.db')
_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    phone          TEXT    DEFAULT '',
    cookie         TEXT    NOT NULL,
    remark         TEXT    DEFAULT '',
    enabled        INTEGER DEFAULT 1,
    last_run       TEXT    DEFAULT '',
    last_ok        INTEGER DEFAULT 0,
    last_signin    INTEGER DEFAULT 0,
    cloud_total    INTEGER DEFAULT 0,
    cloud_received INTEGER DEFAULT 0,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id     INTEGER,
    phone          TEXT    DEFAULT '',
    ok             INTEGER DEFAULT 0,
    signin         INTEGER DEFAULT 0,
    cloud_total    INTEGER DEFAULT 0,
    cloud_received INTEGER DEFAULT 0,
    log            TEXT    DEFAULT '',
    trigger        TEXT    DEFAULT 'manual',
    started_at     TEXT,
    finished_at    TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_account ON runs(account_id);
"""


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    with _lock:
        conn = connect()
        try:
            conn.executescript(SCHEMA)
            for key, value in DEFAULT_SETTINGS.items():
                conn.execute('INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)', (key, str(value)))
            conn.commit()
        finally:
            conn.close()


def get_setting(key, default=''):
    with _lock:
        conn = connect()
        try:
            row = conn.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
            return row['value'] if row else default
        finally:
            conn.close()


def set_settings(pairs: dict):
    with _lock:
        conn = connect()
        try:
            for key, value in pairs.items():
                conn.execute(
                    'INSERT INTO settings(key, value) VALUES (?, ?) '
                    'ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                    (key, str(value)),
                )
            conn.commit()
        finally:
            conn.close()


def all_settings():
    with _lock:
        conn = connect()
        try:
            rows = conn.execute('SELECT key, value FROM settings').fetchall()
        finally:
            conn.close()
    data = dict(DEFAULT_SETTINGS)
    for row in rows:
        data[row['key']] = row['value']
    return data


# ------------------------- 账号 -------------------------

def list_accounts():
    with _lock:
        conn = connect()
        try:
            rows = conn.execute('SELECT * FROM accounts ORDER BY id').fetchall()
        finally:
            conn.close()
    return [dict(r) for r in rows]


def get_account(aid):
    with _lock:
        conn = connect()
        try:
            row = conn.execute('SELECT * FROM accounts WHERE id=?', (aid,)).fetchone()
        finally:
            conn.close()
    return dict(row) if row else None


def add_account(cookie, phone='', remark=''):
    with _lock:
        conn = connect()
        try:
            cur = conn.execute(
                'INSERT INTO accounts(phone, cookie, remark, created_at) VALUES (?,?,?,?)',
                (phone, cookie, remark, _now()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def update_account(aid, **fields):
    if not fields:
        return
    keys = ', '.join(f'{k}=?' for k in fields)
    values = list(fields.values()) + [aid]
    with _lock:
        conn = connect()
        try:
            conn.execute(f'UPDATE accounts SET {keys} WHERE id=?', values)
            conn.commit()
        finally:
            conn.close()


def delete_account(aid):
    with _lock:
        conn = connect()
        try:
            conn.execute('DELETE FROM accounts WHERE id=?', (aid,))
            conn.execute('DELETE FROM runs WHERE account_id=?', (aid,))
            conn.commit()
        finally:
            conn.close()


# ------------------------- 运行记录 -------------------------

def add_run(account_id, result, trigger='manual'):
    with _lock:
        conn = connect()
        try:
            conn.execute(
                'INSERT INTO runs(account_id, phone, ok, signin, cloud_total, cloud_received, log, trigger, started_at, finished_at)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (
                    account_id,
                    result.get('account', ''),
                    1 if result.get('ok') else 0,
                    1 if result.get('signin') else 0,
                    int(result.get('cloud_total') or 0),
                    int(result.get('cloud_received') or 0),
                    result.get('log', '') or '',
                    trigger,
                    result.get('started_at') or _now(),
                    _now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def list_runs(account_id=None, limit=200):
    with _lock:
        conn = connect()
        try:
            if account_id:
                rows = conn.execute(
                    'SELECT id, account_id, phone, ok, signin, cloud_total, cloud_received, trigger, started_at, finished_at'
                    ' FROM runs WHERE account_id=? ORDER BY id DESC LIMIT ?', (account_id, limit)).fetchall()
            else:
                rows = conn.execute(
                    'SELECT id, account_id, phone, ok, signin, cloud_total, cloud_received, trigger, started_at, finished_at'
                    ' FROM runs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        finally:
            conn.close()
    return [dict(r) for r in rows]


def get_run(run_id):
    with _lock:
        conn = connect()
        try:
            row = conn.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
        finally:
            conn.close()
    return dict(row) if row else None


def stats():
    """面板概览数据"""
    accounts = list_accounts()
    with _lock:
        conn = connect()
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            today_got = conn.execute(
                "SELECT COALESCE(SUM(cloud_received),0) c, COUNT(*) n FROM runs WHERE date(started_at)=?",
                (today,)).fetchone()
            last = conn.execute('SELECT MAX(started_at) t FROM runs').fetchone()
        finally:
            conn.close()
    return {
        'account_total': len(accounts),
        'account_enabled': sum(1 for a in accounts if a['enabled']),
        'account_ok': sum(1 for a in accounts if a['last_ok']),
        'bean_total': sum(int(a['cloud_total'] or 0) for a in accounts),
        'bean_today': int(today_got['c'] or 0),
        'run_today': int(today_got['n'] or 0),
        'last_run': last['t'] if last and last['t'] else '',
    }
