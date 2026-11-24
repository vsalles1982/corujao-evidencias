"""Cálculo canônico das seis chaves de identidade contratuais.

Algoritmo normativo (Revisão 010, preservado pela Revisão 018):
  1. normalização Unicode NFC de chaves e valores textualis;
  2. IATA/códigos de companhia em maiúsculas, flight_number sem espaços;
  3. datas YYYY-MM-DD e timestamps UTC YYYY-MM-DDTHH:MM:SSZ;
  4. ordenação recursiva das chaves por ponto de código (sort_keys=True);
  5. JSON compacto, ensure_ascii=False, allow_nan=False, sem newline;
  6. SHA-256 em hex minúsculo com prefixo por versão de contrato.

Campo ausente = chave omitida. Campo nulo = chave presente com null.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

PREFIX_QUERY_CONTEXT = "qctx_v2_"
PREFIX_QUOTE_CONTEXT = "gq_v2_"
PREFIX_QUOTE_SOURCE_ID = "gu_v2_"
PREFIX_UNLINKED_LOCAL = "ul_v1_"
PREFIX_QUOTE_COMPARISON = "qc_v2_"
PREFIX_OFFER = "io_v1_"
PREFIX_CANONICAL_FLIGHT = "cf_v1_"


class ContractError(ValueError):
    """Violação de um contrato fechado de identidade."""


def normalize(value: Any) -> Any:
    """Aplica NFC a textos e normaliza recipientes de forma recursiva."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {unicodedata.normalize("NFC", str(k)): normalize(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize(v) for v in value]
    return value


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialização canônica: compacta, ordenada, UTF-8 direto, sem NaN."""
    return json.dumps(
        normalize(payload),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(prefix: str, payload: Mapping[str, Any]) -> tuple[str, str]:
    """Retorna (chave com prefixo, payload canônico em texto)."""
    raw = canonical_json(payload)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest(), raw


def iata(value: str) -> str:
    code = unicodedata.normalize("NFC", value).strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code):
        raise ContractError(f"Código IATA inválido: {value!r}")
    return code


def airline_code(value: str) -> str:
    code = unicodedata.normalize("NFC", value).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,3}", code):
        raise ContractError(f"Código de companhia inválido: {value!r}")
    return code


def flight_number(value: str) -> str:
    number = re.sub(r"\s+", "", unicodedata.normalize("NFC", value)).upper()
    if not number:
        raise ContractError("flight_number não pode ser vazio")
    return number


def date_only(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError) as exc:
        raise ContractError(f"Data inválida (esperado YYYY-MM-DD): {value!r}") from exc
    return value


def utc_seconds(value: str) -> str:
    """Aceita Z ou offset e devolve UTC em segundos, sem fração."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ContractError(f"Timestamp UTC inválido: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"Timestamp sem fuso: {value!r}")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def passengers(adults: int, children: int = 0, infants: int = 0) -> dict[str, int]:
    values = {"adults": adults, "children": children, "infants": infants}
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in values.values()):
        raise ContractError("Passageiros devem ser inteiros não negativos")
    if values["adults"] < 1:
        raise ContractError("É obrigatório pelo menos um adulto")
    return values


def query_context_hash(direct_only: bool, max_stops: int | None, market: str) -> str:
    """Filtros estáveis da consulta. sort e locale são metadados de apresentação."""
    if not isinstance(direct_only, bool):
        raise ContractError("direct_only deve ser booleano")
    if max_stops is not None and (not isinstance(max_stops, int) or isinstance(max_stops, bool)):
        raise ContractError("max_stops deve ser inteiro ou null")
    payload = {
        "v": 2,
        "direct_only": direct_only,
        "max_stops": max_stops,
        "market": unicodedata.normalize("NFC", market).upper(),
    }
    return digest(PREFIX_QUERY_CONTEXT, payload)[0]


def _quote_payload(
    *,
    path: str,
    source_code: str,
    origin_iata: str,
    destination_iata: str,
    departure_date: str,
    return_date: str | None,
    trip_type: str,
    passengers_value: Mapping[str, int],
    cabin: str,
    query_context: str | None,
    source_query_id: str | None,
) -> dict[str, Any]:
    if path not in {"context", "source_id", "unlinked"}:
        raise ContractError(f"path inválido: {path!r}")
    if trip_type not in {"oneway", "roundtrip"}:
        raise ContractError(f"trip_type inválido: {trip_type!r}")
    if trip_type == "oneway" and return_date is not None:
        raise ContractError("oneway exige return_date nulo")
    if trip_type == "roundtrip" and return_date is None:
        raise ContractError("roundtrip exige return_date não nulo")
    if return_date is not None:
        date_only(return_date)

    # O caso unlinked_local tem contrato próprio (v1). Os Caminhos A e B
    # permanecem em v2, com payloads e vetores normativos inalterados.
    payload: dict[str, Any] = {
        "identity_version": "v1" if path == "unlinked" else "v2",
        "path": path,
        "source_code": unicodedata.normalize("NFC", source_code).lower(),
        "origin_iata": iata(origin_iata),
        "destination_iata": iata(destination_iata),
        "departure_date": date_only(departure_date),
        "return_date": return_date,
        "trip_type": trip_type,
        "passengers": dict(passengers_value),
        "cabin": unicodedata.normalize("NFC", cabin).lower(),
    }
    if path == "context":
        if not query_context:
            raise ContractError("Caminho A exige query_context_hash")
        payload["query_context_hash"] = query_context
    elif path == "source_id":
        if not source_query_id:
            raise ContractError("Caminho B exige source_query_id")
        payload["source_query_id"] = unicodedata.normalize("NFC", source_query_id)
    elif query_context or source_query_id:
        raise ContractError("unlinked_local não admite contexto nem ID estável")
    if path == "unlinked":
        payload["link_status"] = "unlinked_local"
    return payload


def quote_identity_hash(
    *,
    path: str,
    source_code: str,
    origin_iata: str,
    destination_iata: str,
    departure_date: str,
    return_date: str | None,
    trip_type: str,
    passengers_value: Mapping[str, int],
    cabin: str,
    query_context: str | None = None,
    source_query_id: str | None = None,
) -> tuple[str, str]:
    """Prefixos: A=gq_v2_, B=gu_v2_, unlinked_local=ul_v1_."""
    payload = _quote_payload(
        path=path,
        source_code=source_code,
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        departure_date=departure_date,
        return_date=return_date,
        trip_type=trip_type,
        passengers_value=passengers_value,
        cabin=cabin,
        query_context=query_context,
        source_query_id=source_query_id,
    )
    if path == "context":
        prefix = PREFIX_QUOTE_CONTEXT
    elif path == "source_id":
        prefix = PREFIX_QUOTE_SOURCE_ID
    else:
        prefix = PREFIX_UNLINKED_LOCAL
    return digest(prefix, payload)


def unlinked_local_identity_hash(
    *,
    source_code: str,
    origin_iata: str,
    destination_iata: str,
    departure_date: str,
    return_date: str | None,
    trip_type: str,
    passengers_value: Mapping[str, int],
    cabin: str,
) -> tuple[str, str]:
    """Identidade local incompleta: sem contexto, sem ID de fonte e sem comparação."""
    return quote_identity_hash(
        path="unlinked",
        source_code=source_code,
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        departure_date=departure_date,
        return_date=return_date,
        trip_type=trip_type,
        passengers_value=passengers_value,
        cabin=cabin,
    )


def quote_comparison_key(quote_payload: Mapping[str, Any]) -> tuple[str, str]:
    """Chave source-agnostic: remove somente source_code.

    Identidades locais incompletas não são vinculáveis e não possuem esta chave.
    """
    if (quote_payload.get("path") == "unlinked"
            or quote_payload.get("link_status") == "unlinked_local"):
        raise ContractError("unlinked_local não possui quote_comparison_key")
    payload = {k: v for k, v in quote_payload.items() if k != "source_code"}
    return digest(PREFIX_QUOTE_COMPARISON, payload)


def _offer_payload(
    *,
    source_code: str,
    origin_iata: str,
    destination_iata: str,
    departure_date: str,
    return_date: str | None,
    trip_type: str,
    marketing_airline: str,
    operating_airline: str | None,
    flight: str,
    legs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if trip_type not in {"oneway", "roundtrip"}:
        raise ContractError(f"trip_type inválido: {trip_type!r}")
    if trip_type == "oneway" and return_date is not None:
        raise ContractError("oneway exige return_date nulo")
    if trip_type == "roundtrip" and return_date is None:
        raise ContractError("roundtrip exige return_date não nulo")

    normalized_legs: list[dict[str, Any]] = []
    for leg in legs:
        normalized_legs.append(
            {
                "segment_index": leg["segment_index"],
                "from_iata": iata(leg["from_iata"]),
                "to_iata": iata(leg["to_iata"]),
                "scheduled_departure_utc": utc_seconds(leg["scheduled_departure_utc"]),
                "scheduled_arrival_utc": utc_seconds(leg["scheduled_arrival_utc"]),
            }
        )
    normalized_legs.sort(key=lambda item: item["segment_index"])

    payload: dict[str, Any] = {
        "identity_version": "v1",
        "source_code": unicodedata.normalize("NFC", source_code).lower(),
        "origin_iata": iata(origin_iata),
        "destination_iata": iata(destination_iata),
        "departure_date": date_only(departure_date),
        "return_date": return_date,
        "trip_type": trip_type,
        "marketing_airline_code": airline_code(marketing_airline),
        "flight_number": flight_number(flight),
        "legs": normalized_legs,
    }
    # operating_airline_code é atributo descritivo: nunca participa da identidade.
    if operating_airline is not None:
        airline_code(operating_airline)
    return payload


def offer_identity_hash(
    *,
    source_code: str,
    origin_iata: str,
    destination_iata: str,
    departure_date: str,
    return_date: str | None,
    trip_type: str,
    marketing_airline: str,
    operating_airline: str | None,
    flight: str,
    legs: Sequence[Mapping[str, Any]],
) -> tuple[str, str]:
    payload = _offer_payload(
        source_code=source_code,
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        departure_date=departure_date,
        return_date=return_date,
        trip_type=trip_type,
        marketing_airline=marketing_airline,
        operating_airline=operating_airline,
        flight=flight,
        legs=legs,
    )
    return digest(PREFIX_OFFER, payload)


def canonical_flight_key(offer_payload: Mapping[str, Any]) -> tuple[str, str]:
    """Remove source_code e operating_airline_code; mantém itinerário e marketing."""
    payload = {
        k: v
        for k, v in offer_payload.items()
        if k not in {"source_code", "operating_airline_code"}
    }
    return digest(PREFIX_CANONICAL_FLIGHT, payload)
