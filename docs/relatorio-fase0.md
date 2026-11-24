# Relatório de entrega — Fase 0 do Corujão

Data: 24/11/2026. Autorização: Solicitação 019 (Product Owner), exclusivamente
para a Fase 0. Produto independente da SuiteViagem oficial.

**Convenção de evidência:** `[Executado]` = comando rodado nesta sessão, com
saída verificável; `[Documental]` = decisão normativa registrada em arquivo,
sem execução correspondente nesta fase. Nenhum item abaixo é considerado
concluído apenas porque um arquivo foi criado.

---

## 1. Árvore do projeto

`[Executado]` Destino verificado **antes** de qualquer criação: o diretório
`/home/vsalles/Projects/SuiteViagemCorujao` não existia. Árvore final (sem
`.venv`, `__pycache__` e `.pyc`):

```text
SuiteViagemCorujao/
├── README.md
├── pyproject.toml
├── config/
│   ├── bootstrap.json
│   └── deployment.toml
├── data/
│   └── corujao.sqlite3
├── docs/
│   ├── contrato-fase0.md
│   ├── evidencia-testes.txt
│   ├── evidencia-verificacao.json
│   ├── relatorio-fase0.md
│   ├── schema-efetivo.sql
│   └── vetores-hash.md
├── scripts/
│   └── corujao.py
├── src/corujao/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── clock.py
│   ├── config.py
│   ├── db.py
│   ├── identity.py
│   ├── migrations.py
│   └── temporal.py
├── tests/
│   └── test_fase0.py
└── .venv/                  (próprio, Python 3.14.8)
```

## 2. Arquivos criados e função

`[Documental]` Função de cada arquivo, conferida pelo conteúdo efetivo:

| Arquivo | Função |
|---|---|
| `pyproject.toml` | metadados, `dependencies = []`, fase 0, fuso e portas registradas |
| `config/deployment.toml` | fuso, janela, bind, porta, SQLite, câmbio pendente e retenção |
| `config/bootstrap.json` | quatro fontes do piloto e 11 chaves de `settings`; sha256 `13b654eb…6852a6` |
| `src/corujao/identity.py` | canonicalização e seis chaves de identidade |
| `src/corujao/migrations.py` | DDL único das nove tabelas, índices e 15 triggers |
| `src/corujao/db.py` | conexão com `foreign_keys`, WAL e `busy_timeout`; relatório de integridade |
| `src/corujao/bootstrap.py` | carga inicial idempotente com `INSERT … ON CONFLICT DO NOTHING` |
| `src/corujao/temporal.py` | `first_seen_at`, sinal de indexação e `lead_time_seconds` |
| `src/corujao/config.py`, `clock.py` | validação de configuração e relógio `America/Sao_Paulo` |
| `scripts/corujao.py` | CLI local `init`, `bootstrap`, `verify` — sem rede e sem servidor |
| `tests/test_fase0.py` | dez testes locais/offline com dados sintéticos |
| `docs/schema-efetivo.sql` | dump real do schema aplicado, sha256 `577a5dd2…f58d1` |
| `docs/evidencia-*.txt/.json` | saídas brutas dos testes e da verificação |

`[Executado]` `pip list` no `.venv`: **apenas `pip==26.2.1`**. Não há
Playwright, Selenium, navegador ou qualquer dependência de coleta. Nenhum
ambiente da suíte oficial foi reutilizado.

## 3. Schema efetivo

`[Executado]` `sqlite3 data/corujao.sqlite3 .schema` gerou
`docs/schema-efetivo.sql` (sha256
`577a5dd28da056d3dd1f28ff6cd99757c1d9662ec43458ff2ce21e929b3f58d1`).

Nove tabelas, exatamente as contratadas:

`schema_migrations`, `bootstraps`, `routes`, `route_dates`, `sources`,
`settings`, `observations`, `generic_quotes`, `identified_offers`.

Tabelas adiadas confirmadas ausentes: `source_configs`, `source_runs`,
`evidence`, `opportunities`, `validations`, `alerts`, `events`.

Estrutura medida: **109 colunas**, **5 índices** (`uq_route_date_oneway`,
`uq_route_date_roundtrip`, `uq_quote_source_id`, `uq_offer_oneway`,
`uq_offer_roundtrip`) e **15 triggers** (imutabilidade, sucessão sem ciclo,
proteção de exclusão, casamento de fonte/rota nas observações, atualização de
`first_seen_at`/`last_seen_at` e restrição de Google Flights a `identified_offers`).

Todas as tabelas usam `STRICT`. Unicidade local de ofertas inclui `legs_json` e
`identity_version`; `return_date` fica fora do índice `oneway`.

## 4. Migrações e bootstrap

`[Executado]` `scripts/corujao.py init` aplicou `['0001']`. Registro em
`schema_migrations`:

```text
0001 | 2026-11-24T09:26:06.805750Z | Cria as nove tabelas da Fase 0, índices parciais e triggers de proteção.
```

`[Executado]` `scripts/corujao.py bootstrap` inseriu quatro fontes e 11
configurações; `scripts/corujao.py verify` aplicou a migração **zero** vezes e
reportou:

```json
{"applied": true, "id": 1, "sha256": "13b654ebb844398c0f4d7d7226ab57ad8c28ee836e9c9f1d605d835b9f6852a6", "applied_at": "2026-11-24T09:26:10.632663Z", "counts": {"routes": 0, "sources": 4, "settings": 11}}
```

`[Executado]` `test_02_bootstrap_sem_duplicacao`: segunda execução do mesmo
arquivo retornou `applied=false`, `reason=bootstrap_ja_aplicado`, com uma única
linha em `bootstraps`. Nenhum `REPLACE` nem atualização indiscriminada foi
usado. SQLite é a fonte de verdade após a carga.

Nota de transparência: detectei, após a primeira criação, que o formato do
timestamp de auditoria estava sem o separador decimal. Corrigi `clock.py` e
reciei o banco recém-gerado, que continha somente a carga automática — nenhum
dado de usuário foi descartado. O registro acima é do banco corrigido.

## 5. Resultados quantitativos

`[Executado]` `.venv/bin/python -m unittest discover -s tests -v`
(saída integral em `docs/evidencia-testes.txt`):

```text
test_01_criacao_inicial_do_banco ................ ok
test_02_bootstrap_sem_duplicacao ................ ok
test_03_migracoes_rastreaveis ................... ok
test_04_integridade_referencial_e_estrutural .... ok
test_05_unicidade_e_protecao_de_identidade ...... ok
test_06_seis_vetores_de_hash .................... ok
test_07_caminhos_a_e_b .......................... ok
test_08_separacao_generic_quote_e_identified_offer ok
test_09_first_seen_indexed_e_lead_time .......... ok
test_10_fontes_estado_inicial_desabilitado ...... ok

Ran 10 tests in 0.105s
OK
```

**10/10 testes aprovados**, sem rede, navegador, porta ou fonte externa.
Os testes cobrem: criação das nove tabelas, idempotência do bootstrap,
rastreabilidade de migração, integridade, unicidade/sucessão, seis vetores,
Caminhos A/B, separação das classes de identidade (incluindo o caso
`unlinked_local` e a restrição de Google Flights), regras temporais e estado
inicial das fontes.

## 6. Seis vetores de identidade

`[Executado]` Recalculados na sessão e comparados com os valores normativos;
detalhes e payloads canônicos em `docs/vetores-hash.md`.

| Chave | Valor | Resultado |
|---|---|---|
| `query_context_hash` | `qctx_v2_37651064cce52afab439d8dae7a8a8e6b7134d6377cedcfb0ee22a6be667aa53` | igual |
| Caminho A | `gq_v2_dfaf7c87ccb96fa313eb1d2db5092fba0a63fcd3c0a1073f1a470aea05416f67` | igual |
| Caminho B | `gu_v2_a06da76bb5222722cd3d0f7143d746f55586dd63d6e19d9d0967545a8f795075` | igual |
| `quote_comparison_key` | `qc_v2_99290a118887f0e242c4e9ed4a2cb687b4b9ce741ae78c968a6a0f55f599c512` | igual |
| `offer_identity_hash` | `io_v1_01dda36b231079809c73147a7268918282a9d770def6368e9db9ec11ef6bd8c1` | igual |
| `canonical_flight_key` | `cf_v1_98ff10b1588997c5d0090dc77f3216f980b48432a1dc86dc7a4822bd5b50ce59` | igual |

`[Documental]` `source_query_id` fica fora do hash no Caminho A;
`query_context_hash` é omitido no Caminho B; `quote_comparison_key` remove
apenas `source_code`; `canonical_flight_key` remove `source_code` e
`operating_airline_code`.

## 7. Integridade SQLite

`[Executado]` Medições na conexão criada por `corujao.db.connect` (saída em
`docs/evidencia-verificacao.json`):

| Verificação | Valor |
|---|---|
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | `[]` (zero violações) |
| `PRAGMA journal_mode` | `wal` |
| `PRAGMA foreign_keys` | `1` |
| `PRAGMA busy_timeout` | `5000` ms |
| versão do SQLite | 3.54.0 |
| tamanho do arquivo | 106.496 bytes |

`[Documental]` `PRAGMA foreign_keys` é configurado **por conexão**: uma
conexão direta feita apenas com `sqlite3` na linha de comando reporta `0`,
por padrão. A garantia desta fase está no módulo `db.py`, usado por todos os
scripts e testes; não existe mecanismo SQLite para gravar essa opção dentro
do arquivo. Isso fica registrado como ponto de atenção para a Fase 1.

## 8. Estado das fontes

`[Executado]` Consulta às quatro linhas de `sources`, ordenadas por `code`:

| Código | Papel no piloto | `evaluation_status` | `operational_enabled` |
|---|---|---|---|
| `decolar` | OTA complementar | `not_evaluated` | `0` |
| `google_flights` | referência de indexação | `not_evaluated` | `0` |
| `latam` | candidata primária | `not_evaluated` | `0` |
| `turismocity` | validadora | `not_evaluated` | `0` |

`[Executado]` Teste 10 confirmou que tentar elevar `operational_enabled` para
`1` é bloqueado por `CHECK`. Nenhuma fonte foi consultada, nenhum coletor foi
escrito ou executado e nenhuma integração foi feita.

`[Documental]` Google Flights fornece apenas sinal de indexação para
`generic_quotes`; trigger dedicado impede sua conversão em
`identified_offer`.

## 9. Suíte oficial intacta

`[Executado]` Em
`/home/vsalles/raspador_voo_hotel_carro_evento/suite-viagem`:

```text
git status --porcelain        → (vazio: árvore limpa)
git branch --show-current     → freeze/web-v3.7.2-champion
git rev-parse HEAD            → ebab472772348222501c741c9559398e3e74b558
git tag --points-at HEAD      → campeao-4x4-v3_11_1-asyncio-fix
```

Nenhum arquivo da suíte foi modificado. Nenhum processo da suíte foi iniciado.
Também não houve verificação de disponibilidade de portas, abertura de
servidor, acesso a sites ou consultas reais.

## 10. Pendências e limites da Fase 0

`[Documental]` Itens que **dependem de autorização própria** e não foram
executados:

1. Integração com fontes, implementação/execução de coletores e testes de
   navegador; nenhuma evasão, fingerprinting, rotação de IP ou bypass de
   CAPTCHA será usado.
2. Interface, agendamento, serviço HTTP e validação de promoções. O bind
   `127.0.0.1` e a porta `8790` estão apenas registrados; porta `8787` é
   proibida. Nenhuma porta foi verificada ou aberta.
3. Fonte cambial e janela de validade: `fx_status = pending_approval`.
4. Política de retenção definitiva: 180 dias é hipótese, sem exclusão
   automática.
5. Tabelas da Fase 1 (`source_configs`, `source_runs`, `evidence`) e das fases
   seguintes (`opportunities`, `validations`, `alerts`, `events`).
6. Alertas somente internos à futura interface do Corujão; nenhum alerta
   externo, publicação ou integração com a suíte. Nenhuma funcionalidade de
   reserva, venda, emissão, pagamento ou pós-compra.
7. Confirmação formal do Tech Lead para o prefixo do caso
   `unlinked_local` (`gu_v2_` com `path='unlinked'`), único vetor não
   publicado na documentação histórica.
8. Revisão do DDL derivado das listas de campos, registrado em
   `docs/schema-efetivo.sql`, e reforço de `foreign_keys` em futuras conexões
   externas ao módulo `db.py`.

**[Encerramento]** A execução para ao final da Fase 0. Os itens acima não
foram interpretados como autorizados pela Solicitação 019.
