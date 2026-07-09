"""
history.py
----------
SQLite-backed analysis session history (ChatGPT-like sidebar).

Each analysis run is saved as one session with the full result payload JSON.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    # row shape: (cid, name, type, notnull, dflt_value, pk)
    return {str(r[1]) for r in rows}


def _ensure_history_schema(conn: sqlite3.Connection) -> None:
    """Best-effort schema sync for the `history` table.

    This repo doesn't use migrations for the SQLite history DB.
    We keep this tiny + idempotent.
    """

    cols = _table_columns(conn, "history")

    # Added later: richer metadata than just `file_names`.
    if "uploaded_files_json" not in cols:
        conn.execute('ALTER TABLE history ADD COLUMN uploaded_files_json TEXT NULL')
    if "output_files_json" not in cols:
        conn.execute('ALTER TABLE history ADD COLUMN output_files_json TEXT NULL')


def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp TEXT NOT NULL,
              vendor_count INTEGER NOT NULL,
              best_vendor TEXT NOT NULL,
              final_score REAL NOT NULL,
              data_json TEXT NOT NULL,
              file_names TEXT NOT NULL,
              uploaded_files_json TEXT NULL,
              output_files_json TEXT NULL
            )
            """
        )
        _ensure_history_schema(conn)
        conn.commit()


def save_session(
    db_path: str,
    vendor_count: int,
    best_vendor: str,
    final_score: float,
    data: Dict[str, Any],
    file_names: List[str],
    uploaded_files: Optional[List[Dict[str, Any]]] = None,
    output_files: Optional[List[Dict[str, Any]]] = None,
) -> int:
    init_db(db_path)
    ts = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(db_path)) as conn:
        cur = conn.execute(
            """
            INSERT INTO history (
              timestamp,
              vendor_count,
              best_vendor,
              final_score,
              data_json,
              file_names,
              uploaded_files_json,
              output_files_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                int(vendor_count),
                str(best_vendor),
                float(final_score),
                json.dumps(data, ensure_ascii=False),
                json.dumps(file_names, ensure_ascii=False),
                json.dumps(uploaded_files or [], ensure_ascii=False),
                json.dumps(output_files or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_sessions(db_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, timestamp, vendor_count, best_vendor, final_score, file_names, uploaded_files_json, output_files_json
            FROM history
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "timestamp": str(r["timestamp"]),
                "vendor_count": int(r["vendor_count"]),
                "best_vendor": str(r["best_vendor"]),
                "final_score": float(r["final_score"]),
                "file_names": json.loads(r["file_names"] or "[]"),
                "uploaded_files": json.loads(r["uploaded_files_json"] or "[]"),
                "output_files": json.loads(r["output_files_json"] or "[]"),
            }
        )
    return out


def get_session(db_path: str, session_id: int) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM history WHERE id = ?",
            (int(session_id),),
        ).fetchone()
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "timestamp": str(row["timestamp"]),
        "vendor_count": int(row["vendor_count"]),
        "best_vendor": str(row["best_vendor"]),
        "final_score": float(row["final_score"]),
        "file_names": json.loads(row["file_names"] or "[]"),
        "uploaded_files": json.loads((row["uploaded_files_json"] if "uploaded_files_json" in row.keys() else None) or "[]"),
        "output_files": json.loads((row["output_files_json"] if "output_files_json" in row.keys() else None) or "[]"),
        "data": json.loads(row["data_json"] or "{}"),
    }


def clear_history(db_path: str) -> None:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("DELETE FROM history")
        conn.commit()

