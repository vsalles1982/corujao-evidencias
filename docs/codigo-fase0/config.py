"""Carregamento e validação da configuração local da Fase 0."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    timezone: str
    window_start: str
    window_end: str
    bind: str
    port: int
    db_path: Path
    journal_mode: str
    busy_timeout_ms: int
    foreign_keys: bool
    fx_status: str

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        config_path = path or PROJECT_ROOT / "config" / "deployment.toml"
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)

        cfg = cls(
            timezone=raw["timezone"],
            window_start=raw["window"]["start"],
            window_end=raw["window"]["end"],
            bind=raw["service"]["bind"],
            port=int(raw["service"]["port"]),
            db_path=(PROJECT_ROOT / raw["database"]["path"]).resolve(),
            journal_mode=raw["database"]["journal_mode"],
            busy_timeout_ms=int(raw["database"]["busy_timeout_ms"]),
            foreign_keys=bool(raw["database"]["foreign_keys"]),
            fx_status=raw["fx"]["status"],
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.timezone != "America/Sao_Paulo":
            raise ValueError("Fuso obrigatório: America/Sao_Paulo")
        if (self.window_start, self.window_end) != ("00:00", "05:00"):
            raise ValueError("Janela padrão obrigatória: 00h–05h")
        if self.bind != "127.0.0.1":
            raise ValueError("Bind obrigatório: 127.0.0.1")
        if self.port == 8787:
            raise ValueError("Porta 8787 é proibida")
        if self.port != 8790:
            raise ValueError("Porta reservada da Fase 0 é 8790")
        if self.journal_mode.upper() != "WAL":
            raise ValueError("journal_mode obrigatório: WAL")
        if self.busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms deve ser positivo")
        if not self.foreign_keys:
            raise ValueError("foreign_keys deve estar habilitado")
