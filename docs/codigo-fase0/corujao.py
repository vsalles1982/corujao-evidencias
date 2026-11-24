#!/usr/bin/env python3
"""CLI local da Fase 0. Não inicia servidor, não abre porta e não acessa fontes externas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from corujao.bootstrap import apply_bootstrap  # noqa: E402
from corujao.config import Config, PROJECT_ROOT  # noqa: E402
from corujao.db import initialize, integrity_report  # noqa: E402
from corujao.migrations import applied_versions  # noqa: E402


def _summary(conn) -> dict[str, object]:
    report = integrity_report(conn)
    report["migrations"] = applied_versions(conn)
    report["sources"] = [
        dict(row)
        for row in conn.execute(
            "SELECT code, kind, pilot_role, evaluation_status, operational_enabled "
            "FROM sources ORDER BY code"
        )
    ]
    report["counts"] = {
        table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in report["tables"]
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Corujão — fundação local da Fase 0")
    parser.add_argument("command", choices=["init", "bootstrap", "verify"])
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "deployment.toml")
    parser.add_argument("--bootstrap", type=Path, default=PROJECT_ROOT / "config" / "bootstrap.json")
    args = parser.parse_args()

    config = Config.load(args.config)
    conn, applied = initialize(config)
    try:
        if args.command == "bootstrap":
            result = apply_bootstrap(conn, args.bootstrap)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        payload = {"new_migrations": applied, **_summary(conn)}
        if args.command != "bootstrap":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
