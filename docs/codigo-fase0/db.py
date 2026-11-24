"""Conexão SQLite e inicialização do banco próprio do Corujão."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import Config
from .migrations import apply_migrations


def connect(path: str | Path, *, busy_timeout_ms: int = 5000) -> sqlite3.Connection:
    """Abre conexão com foreign_keys, WAL e busy_timeout já aplicados."""
    conn = sqlite3.connect(str(path), timeout=busy_timeout_ms / 1000, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize(config: Config) -> tuple[sqlite3.Connection, list[str]]:
    """Cria/prepare o banco e aplica migrações pendentes."""
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(config.db_path, busy_timeout_ms=config.busy_timeout_ms)
    versions = apply_migrations(conn)
    return conn, versions


def integrity_report(conn: sqlite3.Connection) -> dict[str, object]:
    """Evidências estruturais e referenciais do banco, somente leitura."""
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    fk = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
    return {
        "tables": tables,
        "table_count": len(tables),
        "foreign_key_violations": fk,
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "foreign_keys": conn.execute("PRAGMA foreign_keys").fetchone()[0],
        "busy_timeout": conn.execute("PRAGMA busy_timeout").fetchone()[0],
    }
