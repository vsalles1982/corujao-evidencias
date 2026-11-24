"""Regras de primeira observação, indexação comprovada e antecedência.

Nenhuma inferência retroativa é permitida. Um sinal só qualifica no momento em
que é recebido: exige identidade comprovada, equivalência já declarada, fonte
existente com papel compatível e metadados completos. Sinais não qualificados
não gravam `indexed_at` e, portanto, não produzem `lead_time_seconds`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

IDENTITY_TABLES = {"generic_quotes": "quote_identity_hash", "identified_offers": "offer_identity_hash"}

# Papel declarado no grupo-piloto. Google Flights é referência de indexação;
# Turismocity é validadora. Outras fontes não qualificam sinais nesta fase.
SOURCE_ROLE_BY_PILOT_ROLE = {"validator": "validator", "reference": "indexer"}

UTC_SECONDS = "%Y-%m-%dT%H:%M:%SZ"


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


def validate_indexing_signal(signal: dict[str, Any]) -> datetime:
    """Valida metadados da Solicitação 018 e devolve o captured_at em UTC."""
    required = {"role", "semantics", "source_code", "captured_at", "contract"}
    missing = required - set(signal)
    if missing:
        raise ValueError(f"Sinal de indexação incompleto: {sorted(missing)}")
    if signal["role"] not in {"indexer", "validator"}:
        raise ValueError("role deve ser 'indexer' ou 'validator'")
    if not str(signal["semantics"]).strip():
        raise ValueError("semantics do sinal é obrigatório")
    if not str(signal["source_code"]).strip():
        raise ValueError("source_code do sinal é obrigatório")
    if not str(signal["contract"]).strip():
        raise ValueError("contract do sinal é obrigatório")
    captured = parse_timestamp(str(signal["captured_at"]))
    if captured is None:
        raise ValueError("captured_at inválido")
    return captured


def _source_role_matches(conn: sqlite3.Connection, source_code: str, role: str) -> bool:
    """A fonte deve existir e ter papel declarado compatível com o sinal."""
    row = conn.execute(
        "SELECT pilot_role FROM sources WHERE code = ?",
        (str(source_code).strip().lower(),),
    ).fetchone()
    if row is None:
        return False
    return SOURCE_ROLE_BY_PILOT_ROLE.get(row["pilot_role"]) == role


def _identity_is_proven(conn: sqlite3.Connection, table: str, identity_id: int) -> bool:
    """Identidade comprovada: linha vinculável com hash do prefixo normativo."""
    if table == "generic_quotes":
        row = conn.execute(
            "SELECT quote_identity_hash, path, link_status FROM generic_quotes WHERE id = ?",
            (identity_id,),
        ).fetchone()
        if row is None or row["path"] not in {"context", "source_id"}:
            return False
        if row["link_status"] not in {"linked_context", "linked_source_id"}:
            return False
        return row["quote_identity_hash"].startswith(("gq_v2_", "gu_v2_"))
    row = conn.execute(
        "SELECT offer_identity_hash FROM identified_offers WHERE id = ?",
        (identity_id,),
    ).fetchone()
    return row is not None and row["offer_identity_hash"].startswith("io_v1_")


def register_indexing_signal(
    conn: sqlite3.Connection,
    table: str,
    identity_id: int,
    observed_at: str,
    signal: dict[str, Any],
) -> bool:
    """Qualifica a primeira observação comprovada em indexador/validador.

    Retorna False, sem gravar nada, se qualquer condição cumulativa falhar.
    """
    if table not in IDENTITY_TABLES:
        raise ValueError(f"Tabela de identidade não permitida: {table}")
    observed = parse_timestamp(observed_at)
    if observed is None:
        raise ValueError("observed_at inválido")
    validate_indexing_signal(signal)

    # `captured_at` é metadado obrigatório do sinal; `indexed_at` continua sendo
    # o `observed_at` da observação qualificada, como na Revisão 018.
    if not _source_role_matches(conn, signal["source_code"], signal["role"]):
        return False

    row = conn.execute(
        f"SELECT first_seen_at, indexed_at, equivalence_status FROM {table} WHERE id = ?",
        (identity_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Identidade não encontrada")
    if row["indexed_at"] is not None:
        return False
    if row["equivalence_status"] != "equivalent":
        return False
    first_seen = parse_timestamp(row["first_seen_at"])
    if first_seen is None or observed < first_seen:
        return False
    if not _identity_is_proven(conn, table, identity_id):
        return False

    conn.execute(
        f"UPDATE {table} SET indexed_at = ?, indexing_signal_json = ? WHERE id = ?",
        (observed.strftime(UTC_SECONDS), json.dumps(signal, sort_keys=True, ensure_ascii=False), identity_id),
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
        identity_valid=_identity_is_proven(conn, table, identity_id),
        equivalence_status=row["equivalence_status"],
        first_seen=row["first_seen_at"],
        indexed=row["indexed_at"],
        indexing_signal_documented=bool(row["indexing_signal_json"]),
    )
    conn.execute(f"UPDATE {table} SET lead_time_seconds = ? WHERE id = ?", (value, identity_id))
    return value
