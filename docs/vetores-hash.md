# Seis vetores de hash — Fase 0

Registro dos vetores canônicos da Revisão 010, recalculados em 24/11/2026 com
Python 3.14.8 e SQLite 3.54.0, sem acesso a fontes externas. Os hashes abaixo
foram produzidos pelo módulo `src/corujao/identity.py` e confirmados pelo teste
`test_06_seis_vetores_de_hash`, que compara também o payload canônico exato,
não apenas o resumo.

## Algoritmo

1. Normalização Unicode **NFC** de chaves e valores textuais.
2. IATA/código de companhia em maiúsculas; `flight_number` sem espaços e com
   zeros à esquerda preservados.
3. Datas em `YYYY-MM-DD`; timestamps UTC em `YYYY-MM-DDTHH:MM:SSZ`.
4. Ordenação recursiva das chaves (`sort_keys=True`).
5. JSON compacto (`separators=(',',':')`), `ensure_ascii=False`,
   `allow_nan=False`, sem newline.
6. SHA-256 em hexadecimal minúsculo, com prefixo da versão do contrato.

Campo ausente = chave **omitida**. Campo nulo = chave **presente** com `null`.

## Vetores

| # | Chave | Valor |
|---|---|---|
| 1 | `query_context_hash` | `qctx_v2_37651064cce52afab439d8dae7a8a8e6b7134d6377cedcfb0ee22a6be667aa53` |
| 2 | Caminho A — `quote_identity_hash` | `gq_v2_dfaf7c87ccb96fa313eb1d2db5092fba0a63fcd3c0a1073f1a470aea05416f67` |
| 3 | Caminho B — `quote_identity_hash` | `gu_v2_a06da76bb5222722cd3d0f7143d746f55586dd63d6e19d9d0967545a8f795075` |
| 4 | `quote_comparison_key` | `qc_v2_99290a118887f0e242c4e9ed4a2cb687b4b9ce741ae78c968a6a0f55f599c512` |
| 5 | `offer_identity_hash` | `io_v1_01dda36b231079809c73147a7268918282a9d770def6368e9db9ec11ef6bd8c1` |
| 6 | `canonical_flight_key` | `cf_v1_98ff10b1588997c5d0090dc77f3216f980b48432a1dc86dc7a4822bd5b50ce59` |

### 1. `query_context_hash`

Payload canônico:

```json
{"direct_only":false,"market":"BR","max_stops":null,"v":2}
```

`sort` e `locale` são metadados de apresentação e não entram no hash.
Ausência de filtro essencial impede comparação entre fontes.

### 2. Caminho A — contexto

Payload canônico:

```json
{"cabin":"economy","departure_date":"2026-12-08","destination_iata":"SAO","identity_version":"v2","origin_iata":"GIG","passengers":{"adults":1,"children":0,"infants":0},"path":"context","query_context_hash":"qctx_v2_37651064cce52afab439d8dae7a8a8e6b7134d6377cedcfb0ee22a6be667aa53","return_date":null,"source_code":"turismocity","trip_type":"oneway"}
```

`source_query_id` não participa do hash neste caminho.

### 3. Caminho B — ID estável da fonte

Payload canônico:

```json
{"cabin":"economy","departure_date":"2026-12-08","destination_iata":"GRU","identity_version":"v2","origin_iata":"GIG","passengers":{"adults":1,"children":0,"infants":0},"path":"source_id","return_date":null,"source_code":"decolar","source_query_id":"sq_dec_77aa910b","trip_type":"oneway"}
```

A chave `query_context_hash` é **omitida**, nunca gravada como `null` canônico.

### 4. `quote_comparison_key`

Payload do vetor 2 com apenas `source_code` removido. Mantém
`path='context'` e `query_context_hash`. Prefixo `qc_v2_`.

### 5. `offer_identity_hash`

Payload canônico:

```json
{"departure_date":"2026-12-08","destination_iata":"GRU","flight_number":"G31381","identity_version":"v1","legs":[{"from_iata":"GIG","scheduled_arrival_utc":"2026-12-09T02:25:00Z","scheduled_departure_utc":"2026-12-09T01:10:00Z","segment_index":1,"to_iata":"GRU"}],"marketing_airline_code":"G3","origin_iata":"GIG","return_date":null,"source_code":"decolar","trip_type":"oneway"}
```

Preço, disponibilidade, bagagem, regras tarifárias e condições comerciais
**não** alteram identidade. `operating_airline_code` é atributo descritivo e
também não participa da identidade.

### 6. `canonical_flight_key`

Payload do vetor 5 com `source_code` e `operating_airline_code` removidos.
Identifica o itinerário, não a tarifa.

## Caso sem contexto e sem ID estável

Não há vetor publicado para esse caso. A implementação usa
`path='unlinked'`, `link_status='unlinked_local'` e o prefixo `gu_v2_`, sem
inventar um novo prefixo e sem usar `incomplete_offer`. Este ponto está
registrado como pendência de confirmação formal em
`docs/contrato-fase0.md` e no relatório.
