"""Carga inicial idempotente a partir de config/bootstrap.json.

O arquivo é apenas semente: depois da carga, SQLite é a fonte de verdade.
Nunca usa REPLACE nem atualização indiscriminada; toda inserção é
INSERT ... ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from .clock import utc_now


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_bootstrap(conn: sqlite3.Connection, path: Path) -> dict[str, Any]:
    """Aplica a carga inicial; repetir o mesmo arquivo não duplica registros."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    sha = file_sha256(path)

    previous = conn.execute(
        "SELECT id, sha256, applied_at, counts_json FROM bootstraps "
        "WHERE source_file = ? AND sha256 = ?",
        (path.name, sha),
    ).fetchone()
    if previous is not None:
        return {
            "applied": False,
            "reason": "bootstrap_ja_aplicado",
            "id": previous["id"],
            "sha256": previous["sha256"],
            "applied_at": previous["applied_at"],
            "counts": json.loads(previous["counts_json"]),
        }

    conn.execute("BEGIN IMMEDIATE")
    try:
        now = utc_now()
        counts = {"routes": 0, "sources": 0, "settings": 0}

        for route in payload.get("routes", []):
            cur = conn.execute(
                "INSERT INTO routes(origin_iata, destination_iata, label, active, "
                "created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(origin_iata, destination_iata) DO NOTHING",
                (
                    route["origin_iata"],
                    route["destination_iata"],
                    route["label"],
                    int(route.get("active", 1)),
                    now,
                    now,
                ),
            )
            counts["routes"] += cur.rowcount

        for source in payload.get("sources", []):
            cur = conn.execute(
                "INSERT INTO sources(code, name, kind, pilot_role, evaluation_status, "
                "evaluation_notes, operational_enabled, terms_url, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, 'not_evaluated', ?, 0, ?, ?, ?) "
                "ON CONFLICT(code) DO NOTHING",
                (
                    source["code"],
                    source["name"],
                    source["kind"],
                    source["pilot_role"],
                    source.get("evaluation_notes"),
                    source.get("terms_url"),
                    now,
                    now,
                ),
            )
            counts["sources"] += cur.rowcount

        for key, entry in payload.get("settings", {}).items():
            cur = conn.execute(
                "INSERT INTO settings(key, value_json, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(key) DO NOTHING",
                (
                    key,
                    json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
                    now,
                ),
            )
            counts["settings"] += cur.rowcount

        cur = conn.execute(
            "INSERT INTO bootstraps(source_file, sha256, applied_at, counts_json) "
            "VALUES(?, ?, ?, ?) ON CONFLICT(source_file, sha256) DO NOTHING",
            (path.name, sha, now, json.dumps(counts, sort_keys=True)),
        )
        result = {
            "applied": True,
            "id": cur.lastrowid,
            "sha256": sha,
            "applied_at": now,
            "counts": counts,
        }
        conn.execute("COMMIT")
        return result
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
