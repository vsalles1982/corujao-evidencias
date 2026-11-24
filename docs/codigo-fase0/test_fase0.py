"""Testes locais/offline da Fase 0 e das correções da Solicitação 020.

Executáveis com: .venv/bin/python -m unittest discover -s tests -v
Nenhum teste acessa rede, navegador, portas ou fontes externas.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from corujao.bootstrap import apply_bootstrap  # noqa: E402
from corujao.config import Config, PROJECT_ROOT  # noqa: E402
from corujao.db import connect, initialize, integrity_report  # noqa: E402
from corujao.identity import (  # noqa: E402
    ContractError,
    canonical_flight_key,
    offer_identity_hash,
    query_context_hash,
    quote_comparison_key,
    quote_identity_hash,
    unlinked_local_identity_hash,
)
from corujao.migrations import apply_migrations  # noqa: E402
from corujao.temporal import (  # noqa: E402
    compute_lead_time,
    first_seen_at,
    recompute_lead_time,
    register_indexing_signal,
)

QCTX_HASH = "qctx_v2_37651064cce52afab439d8dae7a8a8e6b7134d6377cedcfb0ee22a6be667aa53"
Q_A = "gq_v2_dfaf7c87ccb96fa313eb1d2db5092fba0a63fcd3c0a1073f1a470aea05416f67"
Q_B = "gu_v2_a06da76bb5222722cd3d0f7143d746f55586dd63d6e19d9d0967545a8f795075"
Q_CMP = "qc_v2_99290a118887f0e242c4e9ed4a2cb687b4b9ce741ae78c968a6a0f55f599c512"
OFFER_HASH = "io_v1_01dda36b231079809c73147a7268918282a9d770def6368e9db9ec11ef6bd8c1"
FLIGHT_KEY = "cf_v1_98ff10b1588997c5d0090dc77f3216f980b48432a1dc86dc7a4822bd5b50ce59"
UL_HASH = "ul_v1_04a9fe3c0fb396d9d211492b3d15d43bab1fa68c00b8401c406934fd473c41b2"
UL_RAW = (
    '{"cabin":"economy","departure_date":"2026-12-08","destination_iata":"GRU",'
    '"identity_version":"v1","link_status":"unlinked_local","origin_iata":"GIG",'
    '"passengers":{"adults":1,"children":0,"infants":0},"path":"unlinked",'
    '"return_date":null,"source_code":"decolar","trip_type":"oneway"}'
)

PAX = {"adults": 1, "children": 0, "infants": 0}
LEGS = [
    {
        "segment_index": 1,
        "from_iata": "GIG",
        "to_iata": "GRU",
        "scheduled_departure_utc": "2026-12-09T01:10:00Z",
        "scheduled_arrival_utc": "2026-12-09T02:25:00Z",
    }
]

EXPECTED_TABLES = {
    "bootstraps",
    "generic_quotes",
    "identified_offers",
    "observations",
    "routes",
    "route_dates",
    "schema_migrations",
    "settings",
    "sources",
}


class Fase0TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Config.load()
        self.config = replace(base, db_path=Path(self.tmp.name) / "corujao.sqlite3")
        self.conn, self.applied = initialize(self.config)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    # --- helpers -------------------------------------------------------
    def source(self, code: str = "decolar", role: str = "complementary_ota") -> int:
        self.conn.execute(
            "INSERT INTO sources(code, name, kind, pilot_role, evaluation_status, "
            "operational_enabled, created_at, updated_at) "
            "VALUES(?, ?, 'ota', ?, 'not_evaluated', 0, '2026-11-24T00:00:00.000Z', "
            "'2026-11-24T00:00:00.000Z') ON CONFLICT(code) DO NOTHING",
            (code, code, role),
        )
        return int(self.conn.execute(
            "SELECT id FROM sources WHERE code = ?", (code,)
        ).fetchone()[0])

    def route_date(self) -> int:
        self.conn.execute(
            "INSERT INTO routes(origin_iata, destination_iata, label, created_at, updated_at) "
            "VALUES('GIG', 'GRU', 'GIG-GRU', '2026-11-24T00:00:00.000Z', "
            "'2026-11-24T00:00:00.000Z') "
            "ON CONFLICT(origin_iata, destination_iata) DO NOTHING"
        )
        route_id = int(self.conn.execute(
            "SELECT id FROM routes WHERE origin_iata = 'GIG' AND destination_iata = 'GRU'"
        ).fetchone()[0])
        self.conn.execute(
            "INSERT INTO route_dates(route_id, departure_date, return_date, trip_type, "
            "query_context_hash, created_at) "
            "VALUES(?, '2026-12-08', NULL, 'oneway', ?, '2026-11-24T00:00:00.000Z') "
            "ON CONFLICT DO NOTHING",
            (route_id, QCTX_HASH),
        )
        return int(self.conn.execute(
            "SELECT id FROM route_dates WHERE route_id = ? AND departure_date = '2026-12-08' "
            "AND trip_type = 'oneway'", (route_id,)
        ).fetchone()[0])

    def quote_row(self, *, source_code: str = "decolar") -> tuple[int, int, int]:
        source_id = self.source(source_code)
        route_date_id = self.route_date()
        value, raw = quote_identity_hash(
            path="context",
            source_code=source_code,
            origin_iata="GIG",
            destination_iata="SAO",
            departure_date="2026-12-08",
            return_date=None,
            trip_type="oneway",
            passengers_value=PAX,
            cabin="economy",
            query_context=QCTX_HASH,
        )
        cur = self.conn.execute(
            "INSERT INTO generic_quotes(quote_identity_hash, identity_version, path, "
            "link_status, route_date_id, source_id, source_code, origin_iata, "
            "destination_iata, departure_date, return_date, trip_type, passengers_json, "
            "cabin, query_context_hash, quote_comparison_key, created_at) "
            "VALUES(?, 'v2', 'context', 'linked_context', ?, ?, ?, 'GIG', 'SAO', "
            "'2026-12-08', NULL, 'oneway', ?, 'economy', ?, ?, "
            "'2026-11-24T00:00:00.000Z')",
            (
                value,
                route_date_id,
                source_id,
                source_code,
                json.dumps(PAX, sort_keys=True),
                QCTX_HASH,
                quote_comparison_key(json.loads(raw))[0],
            ),
        )
        return int(cur.lastrowid), source_id, route_date_id

    def offer_row(self, *, source_code: str = "decolar") -> tuple[int, int, int]:
        source_id = self.source(source_code)
        route_date_id = self.route_date()
        value, raw = offer_identity_hash(
            source_code=source_code,
            origin_iata="GIG",
            destination_iata="GRU",
            departure_date="2026-12-08",
            return_date=None,
            trip_type="oneway",
            marketing_airline="G3",
            operating_airline=None,
            flight="G31381",
            legs=LEGS,
        )
        cur = self.conn.execute(
            "INSERT INTO identified_offers(offer_identity_hash, identity_version, "
            "route_date_id, source_id, source_code, origin_iata, destination_iata, "
            "departure_date, return_date, trip_type, marketing_airline_code, flight_number, "
            "legs_json, canonical_flight_key, created_at) "
            "VALUES(?, 'v1', ?, ?, ?, 'GIG', 'GRU', '2026-12-08', NULL, 'oneway', "
            "'G3', 'G31381', ?, ?, '2026-11-24T00:00:00.000Z')",
            (
                value,
                route_date_id,
                source_id,
                source_code,
                json.dumps(LEGS, sort_keys=True),
                canonical_flight_key(json.loads(raw))[0],
            ),
        )
        return int(cur.lastrowid), source_id, route_date_id

    # --- dez testes autorizados ---------------------------------------
    def test_01_criacao_inicial_do_banco(self) -> None:
        report = integrity_report(self.conn)
        self.assertEqual(self.applied, ["0001", "0002"])
        self.assertEqual(set(report["tables"]), EXPECTED_TABLES)
        self.assertEqual(report["table_count"], 9)

    def test_02_bootstrap_sem_duplicacao(self) -> None:
        path = PROJECT_ROOT / "config" / "bootstrap.json"
        first = apply_bootstrap(self.conn, path)
        second = apply_bootstrap(self.conn, path)
        self.assertTrue(first["applied"])
        self.assertFalse(second["applied"])
        self.assertEqual(second["reason"], "bootstrap_ja_aplicado")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM bootstraps").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sources").fetchone()[0], 4)

    def test_03_migracoes_rastreaveis(self) -> None:
        self.assertEqual(apply_migrations(self.conn), [])
        rows = list(self.conn.execute("SELECT version, description FROM schema_migrations"))
        self.assertEqual([row["version"] for row in rows], ["0001", "0002"])
        self.assertIn("nove tabelas", rows[0]["description"])
        self.assertIn("sources.operational_enabled", rows[1]["description"])

    def test_04_integridade_referencial_e_estrutural(self) -> None:
        report = integrity_report(self.conn)
        self.assertEqual(report["integrity_check"], "ok")
        self.assertEqual(report["foreign_key_violations"], [])
        self.assertEqual(report["foreign_keys"], 1)
        self.assertEqual(report["busy_timeout"], 5000)
        self.assertEqual(report["journal_mode"], "wal")

    def test_05_unicidade_e_protecao_de_identidade(self) -> None:
        offer_id, _, _ = self.offer_row()
        with self.assertRaises(sqlite3.IntegrityError):
            self.offer_row()  # mesma identidade e mesmos campos de unicidade
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE identified_offers SET offer_identity_hash = ? WHERE id = ?",
                ("io_v1_mudanca", offer_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE identified_offers SET superseded_by_hash = offer_identity_hash "
                "WHERE id = ?",
                (offer_id,),
            )
        successor = self.offer_row(source_code="latam")[0]
        self.conn.execute(
            "UPDATE identified_offers SET superseded_by_hash = ? WHERE id = ?",
            (self.conn.execute(
                "SELECT offer_identity_hash FROM identified_offers WHERE id = ?",
                (successor,),
            ).fetchone()[0], offer_id),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM identified_offers WHERE id = ?", (offer_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE identified_offers SET superseded_by_hash = ? WHERE id = ?",
                ("io_v1_terceira", offer_id),
            )

    def test_06_seis_vetores_de_hash(self) -> None:
        from corujao.identity import canonical_json, digest, PREFIX_QUERY_CONTEXT

        ctx_hash, ctx_raw = digest(
            PREFIX_QUERY_CONTEXT,
            {"v": 2, "direct_only": False, "market": "BR", "max_stops": None},
        )
        self.assertEqual(ctx_hash, query_context_hash(False, None, "BR"))
        self.assertEqual(ctx_hash, QCTX_HASH)
        self.assertEqual(ctx_raw, '{"direct_only":false,"market":"BR","max_stops":null,"v":2}')

        a_hash, a_raw = quote_identity_hash(
            path="context", source_code="turismocity", origin_iata="GIG",
            destination_iata="SAO", departure_date="2026-12-08", return_date=None,
            trip_type="oneway", passengers_value=PAX, cabin="economy", query_context=ctx_hash,
        )
        self.assertEqual(a_hash, Q_A)
        self.assertEqual(
            a_raw,
            '{"cabin":"economy","departure_date":"2026-12-08","destination_iata":"SAO",'
            '"identity_version":"v2","origin_iata":"GIG","passengers":{"adults":1,'
            '"children":0,"infants":0},"path":"context","query_context_hash":"' + QCTX_HASH + '",'
            '"return_date":null,"source_code":"turismocity","trip_type":"oneway"}',
        )

        b_hash, b_raw = quote_identity_hash(
            path="source_id", source_code="decolar", origin_iata="GIG",
            destination_iata="GRU", departure_date="2026-12-08", return_date=None,
            trip_type="oneway", passengers_value=PAX, cabin="economy",
            source_query_id="sq_dec_77aa910b",
        )
        self.assertEqual(b_hash, Q_B)
        self.assertEqual(
            b_raw,
            '{"cabin":"economy","departure_date":"2026-12-08","destination_iata":"GRU",'
            '"identity_version":"v2","origin_iata":"GIG","passengers":{"adults":1,'
            '"children":0,"infants":0},"path":"source_id","return_date":null,'
            '"source_code":"decolar","source_query_id":"sq_dec_77aa910b",'
            '"trip_type":"oneway"}',
        )
        cmp_hash, cmp_raw = quote_comparison_key(json.loads(a_raw))
        self.assertEqual(cmp_hash, Q_CMP)
        self.assertNotIn("source_code", cmp_raw)
        self.assertIn("query_context_hash", cmp_raw)

        o_hash, o_raw = offer_identity_hash(
            source_code="decolar", origin_iata="GIG", destination_iata="GRU",
            departure_date="2026-12-08", return_date=None, trip_type="oneway",
            marketing_airline="G3", operating_airline=None, flight="G31381", legs=LEGS,
        )
        self.assertEqual(o_hash, OFFER_HASH)
        f_hash, f_raw = canonical_flight_key(json.loads(o_raw))
        self.assertEqual(f_hash, FLIGHT_KEY)
        self.assertNotIn("source_code", f_raw)
        self.assertNotIn("operating_airline_code", f_raw)
        self.assertEqual(canonical_json(json.loads(o_raw)), o_raw)
        self.assertEqual(len({ctx_hash, a_hash, b_hash, cmp_hash, o_hash, f_hash}), 6)

    def test_07_caminhos_a_e_b(self) -> None:
        a_hash, a_raw = quote_identity_hash(
            path="context", source_code="turismocity", origin_iata="GIG",
            destination_iata="SAO", departure_date="2026-12-08", return_date=None,
            trip_type="oneway", passengers_value=PAX, cabin="economy", query_context=QCTX_HASH,
        )
        b_hash, b_raw = quote_identity_hash(
            path="source_id", source_code="decolar", origin_iata="GIG",
            destination_iata="GRU", departure_date="2026-12-08", return_date=None,
            trip_type="oneway", passengers_value=PAX, cabin="economy",
            source_query_id="sq_dec_77aa910b",
        )
        a_payload, b_payload = json.loads(a_raw), json.loads(b_raw)
        self.assertIn("query_context_hash", a_payload)
        self.assertNotIn("source_query_id", a_payload)
        self.assertIn("source_query_id", b_payload)
        self.assertNotIn("query_context_hash", b_payload)
        self.assertTrue(a_hash.startswith("gq_v2_"))
        self.assertTrue(b_hash.startswith("gu_v2_"))
        with self.assertRaises(ValueError):
            quote_identity_hash(
                path="context", source_code="x", origin_iata="GIG",
                destination_iata="GRU", departure_date="2026-12-08", return_date=None,
                trip_type="oneway", passengers_value=PAX, cabin="economy", query_context=None,
            )

    def test_08_separacao_generic_quote_e_identified_offer(self) -> None:
        quote_id, source_id, route_date_id = self.quote_row()
        offer_id, _, _ = self.offer_row()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO observations(route_date_id, source_id, kind, identity_version, "
                "identity_hash, generic_quote_id, identified_offer_id, observed_at, created_at) "
                "VALUES(?, ?, 'generic_quote', 'v2', 'x', ?, ?, "
                "'2026-11-24T01:00:00Z', '2026-11-24T02:00:00Z')",
                (route_date_id, source_id, quote_id, offer_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO observations(route_date_id, source_id, kind, identity_version, "
                "identity_hash, generic_quote_id, identified_offer_id, observed_at, created_at) "
                "VALUES(?, ?, 'identified_offer', 'v1', 'x', ?, ?, "
                "'2026-11-24T01:00:00Z', '2026-11-24T02:00:00Z')",
                (route_date_id, source_id, quote_id, offer_id),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO identified_offers(offer_identity_hash, identity_version, "
                "route_date_id, source_id, source_code, origin_iata, destination_iata, "
                "departure_date, trip_type, marketing_airline_code, flight_number, "
                "legs_json, canonical_flight_key, created_at) "
                "VALUES('io_v1_google', 'v1', ?, ?, 'google_flights', 'GIG', 'GRU', "
                "'2026-12-08', 'oneway', 'G3', 'G31381', '[]', 'cf_v1_google', "
                "'2026-11-24T00:00:00.000Z')",
                (route_date_id, self.source("google_flights", "reference")),
            )
        unlinked_hash, _ = unlinked_local_identity_hash(
            source_code="decolar", origin_iata="GIG", destination_iata="GRU",
            departure_date="2026-12-08", return_date=None, trip_type="oneway",
            passengers_value=PAX, cabin="economy",
        )
        self.assertTrue(unlinked_hash.startswith("ul_v1_"))
        self.conn.execute(
            "INSERT INTO observations(route_date_id, source_id, kind, identity_version, "
            "identity_hash, observed_at, price_minor, currency, created_at) "
            "VALUES(?, ?, 'unlinked_local', 'v1', ?, "
            "'2026-11-24T01:00:00Z', 119000, 'BRL', '2026-11-24T01:01:00Z')",
            (route_date_id, source_id, unlinked_hash),
        )
        local = self.conn.execute(
            "SELECT kind, identity_version, identity_hash, generic_quote_id, "
            "identified_offer_id FROM observations WHERE kind = 'unlinked_local'"
        ).fetchone()
        self.assertEqual(local["identity_hash"], UL_HASH)
        self.assertEqual(local["identity_version"], "v1")
        self.assertIsNone(local["generic_quote_id"])
        self.assertIsNone(local["identified_offer_id"])
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM generic_quotes WHERE quote_identity_hash = ?",
                (unlinked_hash,),
            ).fetchone()[0],
            0,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO generic_quotes(quote_identity_hash, identity_version, path, "
                "link_status, route_date_id, source_id, source_code, origin_iata, "
                "destination_iata, departure_date, trip_type, passengers_json, cabin, created_at) "
                "VALUES(?, 'v1', 'unlinked', 'unlinked_local', ?, ?, 'decolar', 'GIG', 'GRU', "
                "'2026-12-08', 'oneway', ?, 'economy', '2026-11-24T00:00:00.000Z')",
                (unlinked_hash, route_date_id, source_id, json.dumps(PAX, sort_keys=True)),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO generic_quotes(quote_identity_hash, identity_version, path, "
                "link_status, route_date_id, source_id, source_code, origin_iata, "
                "destination_iata, departure_date, trip_type, passengers_json, cabin, "
                "query_context_hash, created_at) "
                "VALUES('gq_v2_invalido', 'v2', 'context', 'unlinked_local', ?, ?, 'decolar', "
                "'GIG', 'GRU', '2026-12-08', 'oneway', ?, 'economy', ?, "
                "'2026-11-24T00:00:00.000Z')",
                (route_date_id, source_id, json.dumps(PAX, sort_keys=True), QCTX_HASH),
            )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM identified_offers WHERE source_code = 'google_flights'"
            ).fetchone()[0],
            0,
        )
        self.assertIsNotNone(quote_id)
        self.assertIsNotNone(offer_id)

    def test_09_first_seen_indexed_e_lead_time(self) -> None:
        quote_id, source_id, route_date_id = self.quote_row()
        self.assertIsNone(first_seen_at([]))
        self.conn.execute(
            "INSERT INTO observations(route_date_id, source_id, kind, identity_version, "
            "identity_hash, generic_quote_id, observed_at, price_minor, currency, created_at) "
            "VALUES(?, ?, 'generic_quote', 'v2', 'gq_test', ?, "
            "'2026-11-24T03:00:00Z', 120000, 'BRL', '2026-11-24T03:01:00Z')",
            (route_date_id, source_id, quote_id),
        )
        self.conn.execute(
            "INSERT INTO observations(route_date_id, source_id, kind, identity_version, "
            "identity_hash, generic_quote_id, observed_at, price_minor, currency, created_at) "
            "VALUES(?, ?, 'generic_quote', 'v2', 'gq_test', ?, "
            "'2026-11-24T01:30:00Z', 118000, 'BRL', '2026-11-24T01:31:00Z')",
            (route_date_id, source_id, quote_id),
        )
        row = self.conn.execute(
            "SELECT first_seen_at, last_seen_at FROM generic_quotes WHERE id = ?", (quote_id,)
        ).fetchone()
        self.assertEqual(row["first_seen_at"], "2026-11-24T01:30:00Z")
        self.assertEqual(row["last_seen_at"], "2026-11-24T03:00:00Z")

        signal = {
            "role": "indexer",
            "semantics": "primeira aparição comprovada no índice da plataforma",
            "source_code": "google_flights",
            "captured_at": "2026-11-24T02:00:00Z",
            "contract": "google-flights-index-v1",
        }
        self.assertTrue(register_indexing_signal(
            self.conn, "generic_quotes", quote_id, "2026-11-24T02:00:00Z", signal
        ))
        self.assertFalse(register_indexing_signal(
            self.conn, "generic_quotes", quote_id, "2026-11-24T02:30:00Z", signal
        ))
        self.assertIsNone(compute_lead_time(
            identity_valid=True, equivalence_status="unknown",
            first_seen="2026-11-24T01:30:00Z", indexed="2026-11-24T02:00:00Z",
            indexing_signal_documented=True,
        ))
        self.assertEqual(recompute_lead_time(self.conn, "generic_quotes", quote_id), None)
        self.conn.execute(
            "UPDATE generic_quotes SET equivalence_status = 'equivalent' WHERE id = ?", (quote_id,)
        )
        self.assertEqual(recompute_lead_time(self.conn, "generic_quotes", quote_id), 1800)

    def test_10_fontes_estado_inicial_desabilitado(self) -> None:
        apply_bootstrap(self.conn, PROJECT_ROOT / "config" / "bootstrap.json")
        rows = list(self.conn.execute(
            "SELECT code, evaluation_status, operational_enabled FROM sources ORDER BY code"
        ))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["evaluation_status"] == "not_evaluated" for r in rows))
        self.assertTrue(all(r["operational_enabled"] == 0 for r in rows))

        # O domínio 0/1 é estrutural, mas nenhuma fonte do piloto é habilitada.
        self.conn.execute(
            "INSERT INTO sources(code, name, kind, pilot_role, operational_enabled, "
            "created_at, updated_at) VALUES('teste_estrutural', 'Teste', 'ota', "
            "'complementary_ota', 1, '2026-11-24T00:00:00.000Z', "
            "'2026-11-24T00:00:00.000Z')"
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT operational_enabled FROM sources WHERE code = 'teste_estrutural'"
            ).fetchone()[0],
            1,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE sources SET operational_enabled = 2 WHERE code = 'teste_estrutural'"
            )
        self.conn.execute("DELETE FROM sources WHERE code = 'teste_estrutural'")
        rows = list(self.conn.execute(
            "SELECT code, evaluation_status, operational_enabled FROM sources ORDER BY code"
        ))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["evaluation_status"] == "not_evaluated" for r in rows))
        self.assertTrue(all(r["operational_enabled"] == 0 for r in rows))

    def test_11_ul_v1_estabilidade_e_distincao(self) -> None:
        # Variações de caixa e de composição Unicode não alteram a identidade.
        first, first_raw = unlinked_local_identity_hash(
            source_code="DECOLAR", origin_iata="gig", destination_iata="gru",
            departure_date="2026-12-08", return_date=None, trip_type="oneway",
            passengers_value=PAX, cabin="ECONOMY",
        )
        second, second_raw = unlinked_local_identity_hash(
            source_code="decolar", origin_iata="GIG", destination_iata="GRU",
            departure_date="2026-12-08", return_date=None, trip_type="oneway",
            passengers_value=PAX, cabin="economy",
        )
        self.assertEqual(first, UL_HASH)
        self.assertEqual(second, UL_HASH)
        self.assertEqual(first_raw, UL_RAW)
        self.assertEqual(second_raw, UL_RAW)
        self.assertTrue(first.startswith("ul_v1_"))

        b_hash, b_raw = quote_identity_hash(
            path="source_id", source_code="decolar", origin_iata="GIG",
            destination_iata="GRU", departure_date="2026-12-08", return_date=None,
            trip_type="oneway", passengers_value=PAX, cabin="economy",
            source_query_id="sq_dec_77aa910b",
        )
        self.assertEqual(b_hash, Q_B)
        self.assertTrue(b_hash.startswith("gu_v2_"))
        self.assertNotEqual(first, b_hash)
        self.assertNotEqual(first_raw, b_raw)

        payload = json.loads(first_raw)
        self.assertEqual(payload["path"], "unlinked")
        self.assertEqual(payload["link_status"], "unlinked_local")
        self.assertEqual(payload["identity_version"], "v1")
        self.assertNotIn("source_query_id", payload)
        self.assertNotIn("query_context_hash", payload)
        with self.assertRaises(ContractError):
            quote_comparison_key(payload)
        with self.assertRaises(ContractError):
            quote_identity_hash(
                path="unlinked", source_code="decolar", origin_iata="GIG",
                destination_iata="GRU", departure_date="2026-12-08", return_date=None,
                trip_type="oneway", passengers_value=PAX, cabin="economy",
                source_query_id="sq_dec_77aa910b",
            )
        with self.assertRaises(ContractError):
            quote_identity_hash(
                path="unlinked", source_code="decolar", origin_iata="GIG",
                destination_iata="GRU", departure_date="2026-12-08", return_date=None,
                trip_type="oneway", passengers_value=PAX, cabin="economy",
                query_context=QCTX_HASH,
            )

    def test_12_migracao_0002_dominio_sources(self) -> None:
        versions = [
            row[0]
            for row in self.conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]
        self.assertEqual(versions, ["0001", "0002"])
        ddl = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'sources'"
        ).fetchone()[0]
        self.assertIn("CHECK (operational_enabled IN (0, 1))", ddl)
        self.assertNotIn("CHECK (operational_enabled = 0)", ddl)
        self.assertEqual(apply_migrations(self.conn), [])
        self.assertEqual(list(self.conn.execute("PRAGMA foreign_key_check")), [])


if __name__ == "__main__":
    unittest.main()
