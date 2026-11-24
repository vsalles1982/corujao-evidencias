"""Regras de primeira observação, indexação comprovada e antecedência.

Nenhuma inferência retroativa é permitida. `indexed_at` só é registrado com
sinal de indexação documentado; `lead_time_seconds` é nulo se qualquer
condição cumulativa falhar.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

IDENTITY_TABLES = {"generic_quotes": "quote_identity_hash", "identified_offers": "offer_identity_hash"}


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def first_seen_at(observed_at_values: Iterable[str | None]) -> str | None:
    """Menor observed_at efetivamente registrado; nunca uma estimativa."""
    valid = [value for value in observed_at_values if parse_timestamp(value) is not None]
    if not valid:
        return None
    return min(valid, key=lambda value: parse_timestamp(value))  # type: ignore[arg-type]


def validate_indexing_signal(signal: dict[str, Any]) -> None:
    required = {"role", "semantics", "source_code", "captured_at", "contract"}
    missing = required - set(signal)
    if missing:
        raise ValueError(f"Sinal de indexação incompleto: {sorted(missing)}")
    if signal["role"] not in {"indexer", "validator"}:
        raise ValueError("role deve ser 'indexer' ou 'validator'")
    if not str(signal["semantics"]).strip():
        raise ValueError("semantics do sinal é obrigatório")
    if parse_timestamp(str(signal["captured_at"])) is None:
        raise ValueError("captured_at inválido")


def register_indexing_signal(
    conn: sqlite3.Connection,
    table: str,
    identity_id: int,
    observed_at: str,
    signal: dict[str, Any],
) -> bool:
    """Registra a primeira observação comprovada em fonte indexadora/validadora."""
    if table not in IDENTITY_TABLES:
        raise ValueError(f"Tabela de identidade não permitida: {table}")
    if parse_timestamp(observed_at) is None:
        raise ValueError("observed_at inválido")
    validate_indexing_signal(signal)

    row = conn.execute(f"SELECT indexed_at FROM {table} WHERE id = ?", (identity_id,)).fetchone()
    if row is None:
        raise ValueError("Identidade não encontrada")
    if row["indexed_at"] is not None:
        return False
    conn.execute(
        f"UPDATE {table} SET indexed_at = ?, indexing_signal_json = ? WHERE id = ?",
        (observed_at, json.dumps(signal, sort_keys=True, ensure_ascii=False), identity_id),
    )
    return True


def compute_lead_time(
    *,
    identity_valid: bool,
    equivalence_status: str | None,
    first_seen: str | None,
    indexed: str | None,
    indexing_signal_documented: bool,
) -> int | None:
    """Antecedência em segundos; nula quando qualquer condição falha."""
    if not identity_valid or equivalence_status != "equivalent":
        return None
    if not indexing_signal_documented:
        return None
    start = parse_timestamp(first_seen)
    end = parse_timestamp(indexed)
    if start is None or end is None or end < start:
        return None
    return int((end - start).total_seconds())


def recompute_lead_time(conn: sqlite3.Connection, table: str, identity_id: int) -> int | None:
    """Recalcula e persiste lead_time_seconds a partir do estado registrado."""
    if table not in IDENTITY_TABLES:
        raise ValueError(f"Tabela de identidade não permitida: {table}")
    row = conn.execute(
        f"SELECT first_seen_at, indexed_at, equivalence_status, indexing_signal_json "
        f"FROM {table} WHERE id = ?",
        (identity_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Identidade não encontrada")
    value = compute_lead_time(
        identity_valid=True,
        equivalence_status=row["equivalence_status"],
        first_seen=row["first_seen_at"],
        indexed=row["indexed_at"],
        indexing_signal_documented=bool(row["indexing_signal_json"]),
    )
    conn.execute(f"UPDATE {table} SET lead_time_seconds = ? WHERE id = ?", (value, identity_id))
    return value
