"""Relógio único do Corujão: UTC para persistência, fuso local para janela."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")


def utc_now() -> str:
    """Timestamp UTC com milissegundos, forma usada nas colunas de auditoria."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def in_default_window(moment: datetime | None = None) -> bool:
    """Janela 00h–05h no fuso America/Sao_Paulo. Não agenda nem dispara coleta."""
    current = (moment or local_now()).astimezone(LOCAL_TZ)
    return current.hour < 5
