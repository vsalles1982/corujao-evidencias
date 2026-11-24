CREATE TABLE schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL,
  description TEXT NOT NULL
) STRICT;
CREATE TABLE bootstraps (
  id INTEGER PRIMARY KEY,
  source_file TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  counts_json TEXT NOT NULL,
  UNIQUE (source_file, sha256)
) STRICT;
CREATE TABLE routes (
  id INTEGER PRIMARY KEY,
  origin_iata TEXT NOT NULL,
  destination_iata TEXT NOT NULL,
  label TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (origin_iata, destination_iata),
  CHECK (length(origin_iata) = 3 AND length(destination_iata) = 3)
) STRICT;
CREATE TABLE route_dates (
  id INTEGER PRIMARY KEY,
  route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE RESTRICT,
  departure_date TEXT NOT NULL,
  return_date TEXT,
  trip_type TEXT NOT NULL CHECK (trip_type IN ('oneway', 'roundtrip')),
  adults INTEGER NOT NULL DEFAULT 1 CHECK (adults >= 1),
  children INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
  infants INTEGER NOT NULL DEFAULT 0 CHECK (infants >= 0),
  cabin TEXT NOT NULL DEFAULT 'economy',
  query_context_hash TEXT,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  CHECK ((trip_type = 'oneway' AND return_date IS NULL)
         OR (trip_type = 'roundtrip' AND return_date IS NOT NULL)),
  CHECK (return_date IS NULL OR departure_date <= return_date)
) STRICT;
CREATE UNIQUE INDEX uq_route_date_oneway
  ON route_dates(route_id, departure_date, adults, children, infants, cabin,
                 COALESCE(query_context_hash, ''))
  WHERE return_date IS NULL;
CREATE UNIQUE INDEX uq_route_date_roundtrip
  ON route_dates(route_id, departure_date, return_date, adults, children,
                 infants, cabin, COALESCE(query_context_hash, ''))
  WHERE return_date IS NOT NULL;
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
CREATE TABLE observations (
  id INTEGER PRIMARY KEY,
  route_date_id INTEGER NOT NULL REFERENCES route_dates(id) ON DELETE RESTRICT,
  source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
  kind TEXT NOT NULL CHECK (kind IN ('generic_quote', 'identified_offer', 'unlinked_local')),
  identity_version TEXT NOT NULL,
  identity_hash TEXT NOT NULL,
  generic_quote_id INTEGER REFERENCES generic_quotes(id) ON DELETE RESTRICT,
  identified_offer_id INTEGER REFERENCES identified_offers(id) ON DELETE RESTRICT,
  observed_at TEXT NOT NULL,
  price_minor INTEGER,
  currency TEXT,
  fx_rate TEXT,
  price_brl_minor INTEGER,
  comparison_basis TEXT,
  equivalence_status TEXT,
  fare_context_json TEXT,
  query_metadata_json TEXT,
  created_at TEXT NOT NULL,
  CHECK (
    (kind = 'generic_quote' AND generic_quote_id IS NOT NULL AND identified_offer_id IS NULL)
    OR (kind = 'identified_offer' AND identified_offer_id IS NOT NULL AND generic_quote_id IS NULL)
    OR (kind = 'unlinked_local' AND generic_quote_id IS NULL AND identified_offer_id IS NULL)
  )
) STRICT;
CREATE TABLE generic_quotes (
  id INTEGER PRIMARY KEY,
  quote_identity_hash TEXT NOT NULL UNIQUE,
  identity_version TEXT NOT NULL CHECK (identity_version = 'v2'),
  path TEXT NOT NULL CHECK (path IN ('context', 'source_id', 'unlinked')),
  link_status TEXT NOT NULL CHECK (link_status IN
    ('linked_context', 'linked_source_id', 'unlinked_local')),
  route_date_id INTEGER NOT NULL REFERENCES route_dates(id) ON DELETE RESTRICT,
  source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
  source_code TEXT NOT NULL,
  origin_iata TEXT NOT NULL,
  destination_iata TEXT NOT NULL,
  departure_date TEXT NOT NULL,
  return_date TEXT,
  trip_type TEXT NOT NULL CHECK (trip_type IN ('oneway', 'roundtrip')),
  passengers_json TEXT NOT NULL,
  cabin TEXT NOT NULL,
  query_context_hash TEXT,
  source_query_id TEXT,
  quote_comparison_key TEXT,
  first_seen_at TEXT,
  indexed_at TEXT,
  last_seen_at TEXT,
  lead_time_seconds INTEGER,
  equivalence_status TEXT NOT NULL DEFAULT 'unknown'
    CHECK (equivalence_status IN ('unknown', 'equivalent', 'fare_divergent', 'not_applicable')),
  indexing_signal_json TEXT,
  superseded_by_hash TEXT REFERENCES generic_quotes(quote_identity_hash) ON DELETE RESTRICT,
  created_at TEXT NOT NULL,
  CHECK (superseded_by_hash IS NULL OR superseded_by_hash <> quote_identity_hash),
  CHECK ((trip_type = 'oneway' AND return_date IS NULL)
         OR (trip_type = 'roundtrip' AND return_date IS NOT NULL)),
  CHECK (
    (path = 'context' AND query_context_hash IS NOT NULL AND link_status = 'linked_context')
    OR (path = 'source_id' AND source_query_id IS NOT NULL AND link_status = 'linked_source_id')
    OR (path = 'unlinked' AND query_context_hash IS NULL AND source_query_id IS NULL
        AND link_status = 'unlinked_local')
  )
) STRICT;
CREATE UNIQUE INDEX uq_quote_source_id
  ON generic_quotes(source_code, source_query_id)
  WHERE path = 'source_id' AND source_query_id IS NOT NULL;
CREATE TABLE identified_offers (
  id INTEGER PRIMARY KEY,
  offer_identity_hash TEXT NOT NULL UNIQUE,
  identity_version TEXT NOT NULL CHECK (identity_version = 'v1'),
  route_date_id INTEGER NOT NULL REFERENCES route_dates(id) ON DELETE RESTRICT,
  source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
  source_code TEXT NOT NULL,
  origin_iata TEXT NOT NULL,
  destination_iata TEXT NOT NULL,
  departure_date TEXT NOT NULL,
  return_date TEXT,
  trip_type TEXT NOT NULL CHECK (trip_type IN ('oneway', 'roundtrip')),
  marketing_airline_code TEXT NOT NULL,
  operating_airline_code TEXT,
  flight_number TEXT NOT NULL,
  legs_json TEXT NOT NULL,
  canonical_flight_key TEXT NOT NULL,
  first_seen_at TEXT,
  indexed_at TEXT,
  last_seen_at TEXT,
  lead_time_seconds INTEGER,
  equivalence_status TEXT NOT NULL DEFAULT 'unknown'
    CHECK (equivalence_status IN ('unknown', 'equivalent', 'fare_divergent', 'not_applicable')),
  indexing_signal_json TEXT,
  superseded_by_hash TEXT REFERENCES identified_offers(offer_identity_hash) ON DELETE RESTRICT,
  created_at TEXT NOT NULL,
  CHECK (superseded_by_hash IS NULL OR superseded_by_hash <> offer_identity_hash),
  CHECK ((trip_type = 'oneway' AND return_date IS NULL)
         OR (trip_type = 'roundtrip' AND return_date IS NOT NULL))
) STRICT;
CREATE UNIQUE INDEX uq_offer_oneway
  ON identified_offers(source_code, origin_iata, destination_iata, departure_date,
                       trip_type, marketing_airline_code, flight_number,
                       legs_json, identity_version)
  WHERE trip_type = 'oneway';
CREATE UNIQUE INDEX uq_offer_roundtrip
  ON identified_offers(source_code, origin_iata, destination_iata, departure_date,
                       return_date, trip_type, marketing_airline_code,
                       flight_number, legs_json, identity_version)
  WHERE trip_type = 'roundtrip';
CREATE TRIGGER trg_io_google_reference_only
BEFORE INSERT ON identified_offers
WHEN NEW.source_code = 'google_flights'
BEGIN
  SELECT RAISE(ABORT, 'Google Flights e referencia de indexacao');
END;
CREATE TRIGGER trg_gq_identity_immutable
BEFORE UPDATE OF quote_identity_hash, quote_comparison_key ON generic_quotes
BEGIN
  SELECT RAISE(ABORT, 'identidade de cotacao e imutavel');
END;
CREATE TRIGGER trg_io_identity_immutable
BEFORE UPDATE OF offer_identity_hash, canonical_flight_key ON identified_offers
BEGIN
  SELECT RAISE(ABORT, 'identidade de oferta e imutavel');
END;
CREATE TRIGGER trg_gq_no_second_successor
BEFORE UPDATE OF superseded_by_hash ON generic_quotes
WHEN OLD.superseded_by_hash IS NOT NULL
BEGIN
  SELECT RAISE(ABORT, 'segunda sucessora nao permitida');
END;
CREATE TRIGGER trg_gq_succession_cycle
BEFORE UPDATE OF superseded_by_hash ON generic_quotes
WHEN NEW.superseded_by_hash IS NOT NULL
BEGIN
  SELECT RAISE(ABORT, 'ciclo de sucessao de identidade')
  WHERE EXISTS (
    WITH RECURSIVE chain(x) AS (
      SELECT NEW.superseded_by_hash
      UNION ALL
      SELECT g.superseded_by_hash FROM generic_quotes g
      JOIN chain ON g.quote_identity_hash = chain.x
      WHERE g.superseded_by_hash IS NOT NULL
    )
    SELECT 1 FROM chain WHERE chain.x = OLD.quote_identity_hash
  );
END;
CREATE TRIGGER trg_io_no_second_successor
BEFORE UPDATE OF superseded_by_hash ON identified_offers
WHEN OLD.superseded_by_hash IS NOT NULL
BEGIN
  SELECT RAISE(ABORT, 'segunda sucessora nao permitida');
END;
CREATE TRIGGER trg_io_succession_cycle
BEFORE UPDATE OF superseded_by_hash ON identified_offers
WHEN NEW.superseded_by_hash IS NOT NULL
BEGIN
  SELECT RAISE(ABORT, 'ciclo de sucessao de identidade')
  WHERE EXISTS (
    WITH RECURSIVE chain(x) AS (
      SELECT NEW.superseded_by_hash
      UNION ALL
      SELECT o.superseded_by_hash FROM identified_offers o
      JOIN chain ON o.offer_identity_hash = chain.x
      WHERE o.superseded_by_hash IS NOT NULL
    )
    SELECT 1 FROM chain WHERE chain.x = OLD.offer_identity_hash
  );
END;
CREATE TRIGGER trg_gq_block_delete_superseded
BEFORE DELETE ON generic_quotes
WHEN OLD.superseded_by_hash IS NOT NULL
     OR EXISTS (SELECT 1 FROM generic_quotes
                WHERE superseded_by_hash = OLD.quote_identity_hash)
BEGIN
  SELECT RAISE(ABORT, 'identidade sucedida nao pode ser excluida');
END;
CREATE TRIGGER trg_io_block_delete_superseded
BEFORE DELETE ON identified_offers
WHEN OLD.superseded_by_hash IS NOT NULL
     OR EXISTS (SELECT 1 FROM identified_offers
                WHERE superseded_by_hash = OLD.offer_identity_hash)
BEGIN
  SELECT RAISE(ABORT, 'identidade sucedida nao pode ser excluida');
END;
CREATE TRIGGER trg_obs_gq_source_match
BEFORE INSERT ON observations
WHEN NEW.generic_quote_id IS NOT NULL
     AND (SELECT source_id FROM generic_quotes WHERE id = NEW.generic_quote_id) <> NEW.source_id
BEGIN
  SELECT RAISE(ABORT, 'fonte da observacao diverge da identidade');
END;
CREATE TRIGGER trg_obs_io_source_match
BEFORE INSERT ON observations
WHEN NEW.identified_offer_id IS NOT NULL
     AND (SELECT source_id FROM identified_offers WHERE id = NEW.identified_offer_id) <> NEW.source_id
BEGIN
  SELECT RAISE(ABORT, 'fonte da observacao diverge da identidade');
END;
CREATE TRIGGER trg_obs_gq_route_match
BEFORE INSERT ON observations
WHEN NEW.generic_quote_id IS NOT NULL
     AND (SELECT route_date_id FROM generic_quotes WHERE id = NEW.generic_quote_id)
         <> NEW.route_date_id
BEGIN
  SELECT RAISE(ABORT, 'rota/data da observacao diverge da identidade');
END;
CREATE TRIGGER trg_obs_io_route_match
BEFORE INSERT ON observations
WHEN NEW.identified_offer_id IS NOT NULL
     AND (SELECT route_date_id FROM identified_offers WHERE id = NEW.identified_offer_id)
         <> NEW.route_date_id
BEGIN
  SELECT RAISE(ABORT, 'rota/data da observacao diverge da identidade');
END;
CREATE TRIGGER trg_obs_gq_first_seen
AFTER INSERT ON observations
WHEN NEW.kind = 'generic_quote'
BEGIN
  UPDATE generic_quotes
     SET first_seen_at = CASE
           WHEN first_seen_at IS NULL OR NEW.observed_at < first_seen_at
           THEN NEW.observed_at ELSE first_seen_at END,
         last_seen_at = CASE
           WHEN last_seen_at IS NULL OR NEW.observed_at > last_seen_at
           THEN NEW.observed_at ELSE last_seen_at END
   WHERE id = NEW.generic_quote_id;
END;
CREATE TRIGGER trg_obs_io_first_seen
AFTER INSERT ON observations
WHEN NEW.kind = 'identified_offer'
BEGIN
  UPDATE identified_offers
     SET first_seen_at = CASE
           WHEN first_seen_at IS NULL OR NEW.observed_at < first_seen_at
           THEN NEW.observed_at ELSE first_seen_at END,
         last_seen_at = CASE
           WHEN last_seen_at IS NULL OR NEW.observed_at > last_seen_at
           THEN NEW.observed_at ELSE last_seen_at END
   WHERE id = NEW.identified_offer_id;
END;
CREATE TABLE "sources" (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('airline', 'ota', 'metasearch')),
  pilot_role TEXT NOT NULL CHECK (pilot_role IN
    ('primary_candidate', 'complementary_ota', 'validator', 'reference')),
  evaluation_status TEXT NOT NULL DEFAULT 'not_evaluated'
    CHECK (evaluation_status IN ('not_evaluated', 'in_evaluation',
                                 'technically_approved', 'rejected', 'blocked')),
  evaluation_notes TEXT,
  operational_enabled INTEGER NOT NULL DEFAULT 0 CHECK (operational_enabled IN (0, 1)),
  terms_url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER trg_gq_no_unlinked_insert
BEFORE INSERT ON generic_quotes
WHEN NEW.path = 'unlinked' OR NEW.link_status = 'unlinked_local'
BEGIN
  SELECT RAISE(ABORT, 'unlinked_local nao e cotacao vinculavel');
END;
CREATE TRIGGER trg_gq_no_unlinked_update
BEFORE UPDATE OF path, link_status ON generic_quotes
WHEN NEW.path = 'unlinked' OR NEW.link_status = 'unlinked_local'
BEGIN
  SELECT RAISE(ABORT, 'unlinked_local nao e cotacao vinculavel');
END;
