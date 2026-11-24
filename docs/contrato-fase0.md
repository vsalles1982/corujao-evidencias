# Contrato implementado — Fase 0

Base normativa: Solicitação 019, Revisão 018 (first_seen_at/indexed_at),
Revisão 017-R (simplificação tarifária), Revisão 010 (vetores e canonicalização)
e HANDOFF_MASTER_corujao.md.

## 1. Nove tabelas

| Tabela | Finalidade implementada |
|---|---|
| `schema_migrations` | versão, data e descrição de cada DDL aplicado; exclusiva para migrações |
| `bootstraps` | sha256 do arquivo-semente, data e contagens da carga inicial |
| `routes` | rota canônica `origin_iata`/`destination_iata` |
| `route_dates` | data, passageiros, cabine e contexto da consulta |
| `sources` | grupo-piloto com papel, avaliação e habilitação separadas |
| `settings` | janela, fuso, retenção hipótese, porta prevista e câmbio pendente |
| `observations` | observação temporal de preço; classe exclusiva por linha |
| `generic_quotes` | cotação genérica, Caminhos A/B e estado `unlinked_local` |
| `identified_offers` | oferta identificada com chave canônica de voo |

Adiadas, corretamente ausentes: `source_configs`, `source_runs`, `evidence`
(Fase 1) e `opportunities`, `validations`, `alerts`, `events` (Fase 2+).

## 2. Identidade

- Caminho A: `quote_identity_hash` com `query_context_hash`, prefixo `gq_v2_`.
- Caminho B: sem contexto, com `source_query_id`, prefixo `gu_v2_`; a chave
  `query_context_hash` é **omitida**, nunca `null` canônico.
- Sem contexto e sem ID estável: `path='unlinked'` e
  `link_status='unlinked_local'`. O texto `incomplete_offer` não existe no enum.
- `quote_comparison_key` usa `qc_v2_` e remove apenas `source_code`.
- `offer_identity_hash` usa `io_v1_` e inclui `source_code`.
- `canonical_flight_key` usa `cf_v1_` e remove `source_code` e
  `operating_airline_code`.
- `source_query_id` está fora do hash no Caminho A; índice parcial
  `uq_quote_source_id` protege somente o Caminho B.
- Unicidade local de ofertas: `uq_offer_oneway` e `uq_offer_roundtrip`,
  ambos com `legs_json` e `identity_version`; `return_date` fora do índice
  oneway.
- Imutabilidade por trigger; sucessão por FK autorreferenciada com
  `ON DELETE RESTRICT`, sem autorreferência, segunda sucessora ou ciclo;
  exclusão de identidade sucedida bloqueada por trigger.

## 3. Temporalidade

- `first_seen_at` é o menor `observed_at` efetivamente registrado, mantido por
  trigger `AFTER INSERT` em `observations`, por identidade e fonte.
- `indexed_at` só é gravado por `register_indexing_signal()`, que exige papel de
  indexador/validador, semântica declarada, `source_code`, `captured_at` e
  contrato da fonte. Primeira observação comprovada vence; não há inferência.
- `lead_time_seconds = indexed_at - first_seen_at`, somente com identidade
  válida, `equivalence_status = 'equivalent'`, timestamps válidos e sinal de
  indexação documentado; `null` caso contrário.
- Cotação genérica nunca afirma descoberta anterior a indexadores; ausência de
  `indexed_at` não prova ausência de indexação na internet.

## 4. Fontes

`latam` (primária candidata), `decolar` (OTA complementar), `turismocity`
(validadora) e `google_flights` (referência). Todas com
`operational_enabled = 0` e `evaluation_status = not_evaluated`. Trigger
dedicado impede que `google_flights` vire `identified_offers`.

## 5. Contradições históricas sinalizadas ao Tech Lead

Estes pontos existem em documentos anteriores e foram resolvidos pela decisão
mais recente; não foram reinterpretados silenciosamente:

1. Documentos antigos descreviam `identity_version = v1` para cotações e o
   estado `incomplete_offer`. Os vetores finais da Revisão 010 usam `v2`, os
   prefixos `gq_v2_`/`gu_v2_` e a Revisão 018/019 fixou `unlinked_local`.
   **Implementado:** forma final.
2. A matriz antiga de equivalência previa auditoria tarifária ampla. A Revisão
  017-R simplificou: `equivalent` exige identidade comprovada e economicidade
  comparável; metadados ausentes viram sinalização; `fare_divergent` fica
  reservado a conflito material declarado. **Implementado:** forma simplificada.
3. Não há vetor publicado para o hash de `unlinked_local`. Foi adotado o prefixo
  `gu_v2_` com `path='unlinked'` explícito, sem inventar novo prefixo.
  **Pendente de confirmação formal do Tech Lead.**
4. não há DDL literal registrado nas revisões anteriores; o esquema foi
   derivado das listas de campos e regras fechadas, com tipagem SQLite
   explícita. `docs/schema-efetivo.sql` registra o resultado para revisão.
