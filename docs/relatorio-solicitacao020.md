# Relatório — Solicitação 020

Fechamento das pendências técnicas da Fase 0 do Corujão. Referência documental:
commit `323086ecab29dd146440a2c67220728ec9fc91a0`. Execução encerrada após
esta entrega.

Convenção: `[Executado]` = comando rodado nesta sessão; `[Documental]` = decisão
normativa aplicada. Os registros da Fase 0 (`relatorio-fase0.md`,
`evidencia-testes.txt`, `evidencia-verificacao.json`) foram preservados.

---

## 1. Resumo das alterações

**Correção A — habilitação futura das fontes.** A migração `0001` não foi
reescrita. A nova migração rastreável `0002` reconstrói `sources` e substitui
`CHECK (operational_enabled = 0)` por `CHECK (operational_enabled IN (0, 1))`.
O domínio `0`/`1` é agora estrutural; nenhuma fonte foi habilitada e todas
continuam com `evaluation_status = 'not_evaluated'`. A migração desliga
`PRAGMA foreign_keys` fora da transação, reconstrói a tabela, restaura o pragma
e valida `PRAGMA foreign_key_check` antes de ser considerada aplicada.

**Correção B — `unlinked_local`.** O prefixo deixou de ser `gu_v2_` (compartilhado
com o Caminho B) e passou a ser exclusivo `ul_v1_`. O payload canônico inclui
`identity_version = "v1"`, `path = "unlinked"` e
`link_status = "unlinked_local"`; não inclui `source_query_id` nem
`query_context_hash`. A identidade passa a ser gravada em `observations`, nunca
em `generic_quotes`. Duas triggers da migração `0002` bloqueiam
`unlinked_local` em `generic_quotes`. `quote_comparison_key` rejeita
explicitamente esse payload. Não há comparação entre fontes, lead time ou
equivalência artificial. Os seis vetores aprovados permanecem idênticos.

**Código efetivo.** Cópias exatas dos módulos e testes foram publicadas em
`docs/codigo-fase0/`, sem reorganizar o projeto local.

## 2. Arquivos modificados e adicionados

`[Executado]` Modificados localmente:

| Arquivo | Alteração |
|---|---|
| `src/corujao/identity.py` | prefixo `ul_v1_`, payload v1 para unlinked, bloqueio de `quote_comparison_key`, helper `unlinked_local_identity_hash()` |
| `src/corujao/migrations.py` | migração `0002`, opção `foreign_keys_off` em `apply_migrations`, duas triggers de separação |
| `tests/test_fase0.py` | ajustes em 01, 03, 08 e 10; novos testes 11 e 12 |
| `docs/contrato-fase0.md` | pendências 3 e 5 marcadas como resolvidas; regras `ul_v1_` e domínio 0/1 |
| `docs/vetores-hash.md` | seção 7 com payload/hash `ul_v1_` e evidências de distinção |
| `docs/schema-efetivo.sql` | dump atualizado após a migração `0002` |
| `README.md` | referências aos novos documentos |

`[Executado]` Adicionados em `docs/`:

- `relatorio-solicitacao020.md` (este arquivo);
- `evidencia-testes-020.txt`, `evidencia-verificacao-020.json`;
- `hashes-sha256-020.txt` (manifesto);
- `codigo-fase0/`: `pyproject.toml`, `corujao.py`, `identity.py`, `migrations.py`,
  `db.py`, `bootstrap.py`, `temporal.py`, `config.py`, `clock.py`,
  `test_fase0.py`.

As dez cópias em `codigo-fase0/` foram comparadas por SHA-256 com os arquivos
locais de origem: **todas iguais**.

## 3. Migrações criadas

`[Executado]` Uma única migração nova:

```text
0002 | Permite 0 e 1 em sources.operational_enabled e separa unlinked_local de generic_quotes.
```

Registro efetivo (aplicada em `2026-11-24T10:06:45.619654Z`). A migração `0001`
permanece com sua data original e descrição original. `scripts/corujao.py init`
aplicou `['0002']` ao banco real; execução posterior reportou `[]`.
`test_12_migracao_0002_dominio_sources` confirma o DDL efetivo e a ausência da
restrição antiga.

DDL verificado: `CHECK (operational_enabled IN (0, 1))` presente;
`CHECK (operational_enabled = 0)` ausente.

## 4. Resultado integral dos testes

`[Executado]` `.venv/bin/python -m unittest discover -s tests -v`
(saída integral em `docs/evidencia-testes-020.txt`):

```text
test_01_criacao_inicial_do_banco (test_fase0.Fase0TestCase.test_01_criacao_inicial_do_banco) ... ok
test_02_bootstrap_sem_duplicacao (test_fase0.Fase0TestCase.test_02_bootstrap_sem_duplicacao) ... ok
test_03_migracoes_rastreaveis (test_fase0.Fase0TestCase.test_03_migracoes_rastreaveis) ... ok
test_04_integridade_referencial_e_estrutural (test_fase0.Fase0TestCase.test_04_integridade_referencial_e_estrutural) ... ok
test_05_unicidade_e_protecao_de_identidade (test_fase0.Fase0TestCase.test_05_unicidade_e_protecao_de_identidade) ... ok
test_06_seis_vetores_de_hash (test_fase0.Fase0TestCase.test_06_seis_vetores_de_hash) ... ok
test_07_caminhos_a_e_b (test_fase0.Fase0TestCase.test_07_caminhos_a_e_b) ... ok
test_08_separacao_generic_quote_e_identified_offer (test_fase0.Fase0TestCase.test_08_separacao_generic_quote_e_identified_offer) ... ok
test_09_first_seen_indexed_e_lead_time (test_fase0.Fase0TestCase.test_09_first_seen_indexed_e_lead_time) ... ok
test_10_fontes_estado_inicial_desabilitado (test_fase0.Fase0TestCase.test_10_fontes_estado_inicial_desabilitado) ... ok
test_11_ul_v1_estabilidade_e_distincao (test_fase0.Fase0TestCase.test_11_ul_v1_estabilidade_e_distincao) ... ok
test_12_migracao_0002_dominio_sources (test_fase0.Fase0TestCase.test_12_migracao_0002_dominio_sources) ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.173s

OK
```

**12/12 aprovados.** Cobertura acrescentada nesta solicitação:

- `test_10`: `0` aceito, `1` estruturalmente aceito em fonte sintética, `2`
  rejeitado, quatro fontes do piloto ainda desabilitadas ao final;
- `test_11`: estabilidade de `ul_v1_` sob variação de caixa/NFC, payload canônico
  exato, distinção do Caminho B (`gu_v2_...`), ausência de contexto/ID e
  rejeição de `quote_comparison_key`;
- `test_12`: presença das migrações `0001`/`0002`, DDL com domínio `0`/`1` e
  `foreign_key_check` limpo.

Hash de referência documentado:
`ul_v1_04a9fe3c0fb396d9d211492b3d15d43bab1fa68c00b8401c406934fd473c41b2`.

## 5. Evidências de integridade SQLite

`[Executado]` Dados de `docs/evidencia-verificacao-020.json`, obtidos pela
conexão criada em `corujao.db.connect`:

| Verificação | Valor |
|---|---|
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | `[]` |
| `PRAGMA journal_mode` | `wal` |
| `PRAGMA foreign_keys` | `1` |
| `PRAGMA busy_timeout` | `5000` ms |
| tabelas | 9 |
| migrações registradas | `0001`, `0002` |
| schema efetivo (sha256) | `4b12034484ee51fa682c6ab141605770f10d3df1e04f2d994e7e1b64249231f0` |

O schema atualizado inclui as triggers `trg_gq_no_unlinked_insert` e
`trg_gq_no_unlinked_update`. `PRAGMA foreign_keys` continua sendo configurado
por conexão; a garantia permanece no módulo `db.py`, como registrado na Fase 0.

## 6. Estados das fontes

`[Executado]` Após a migração e a carga inicial:

| Código | `evaluation_status` | `operational_enabled` |
|---|---|---|
| `decolar` | `not_evaluated` | `0` |
| `google_flights` | `not_evaluated` | `0` |
| `latam` | `not_evaluated` | `0` |
| `turismocity` | `not_evaluated` | `0` |

Nenhuma foi habilitada. A permissão estrutural do valor `1` não é autorização
operacional. O bootstrap permanece com uma única linha e não foi reaplicado.

## 7. Hashes SHA-256 dos arquivos publicados

`[Executado]` Manifesto completo em `docs/hashes-sha256-020.txt`, gerado ao
final da execução. Ele lista todos os arquivos de `docs/` — inclusive as cópias
em `codigo-fase0/` e as evidências — exceto o próprio manifesto, que não pode
conter o próprio hash.

Hashes das cópias do código (iguais aos arquivos locais):

| Arquivo publicado | SHA-256 |
|---|---|
| `codigo-fase0/pyproject.toml` | `7cc0647cd7a37784fb7890b43412bbec086f65fa427954065d130a10927f7c52` |
| `codigo-fase0/corujao.py` | `e8a710fc6ffbd1aae4f8d1cd69899d2b21d367eccb2e4866973cc7d201ab8a19` |
| `codigo-fase0/identity.py` | `987ddcaa82d9c8c3a96ff5c2c7fea71db0f1e534ceeaa07db820023baad3ae56` |
| `codigo-fase0/migrations.py` | `564c86f45a4779136070680c730a28088f12dd1753a3857b98dfe2b775154c51` |
| `codigo-fase0/db.py` | `77d7024401543303806307653133272696ce6730ff9573d56d94fd9241cbce39` |
| `codigo-fase0/bootstrap.py` | `f20acd15758679e81cc596fff0bfa5c80e7e524fe978893bbd4531d6802b0bac` |
| `codigo-fase0/temporal.py` | `25e20b2e6cc231e813481c0cd48a8712ff73d89f2256dac34ebf5e413f92fc7c` |
| `codigo-fase0/config.py` | `3cb35a72b7b97190336f97e9cbf979ed97bd2e99afdf5ad755e7e77fe20bfda3` |
| `codigo-fase0/clock.py` | `e84ce7155e50e2bf871bf702448e235afd90768cd7c7fef747fd599f0302cb2c` |
| `codigo-fase0/test_fase0.py` | `2461968cd06d158506a3cabb31459f73e2f77643d5d0449cea73aac79e5e6b2b` |

## 8. Commit final do GitHub

`[Executado]` Publicação em `vsalles1982/corujao-evidencias`, ramo `main`, sem
apagar os registros históricos da Solicitação 019. O hash do commit final é
informado na resposta de entrega desta solicitação e fica visível em
`git log -1` do repositório. Nenhum banco de dados, credencial, segredo ou
`.venv` foi publicado.

## 9. Pendências remanescentes

`[Documental]` Nenhuma pendência técnica da Solicitação 020 permanece. Restam
as pendências de escopo já registradas na Fase 0, todas dependentes de
autorização própria: Fase 1, coletores, integrações, interface, agendamento,
validação de promoções, fonte cambial aprovada e política de retenção
definitiva. A aceitação definitiva da Fase 0 continua sob responsabilidade do
Tech Lead; esta entrega não autoriza a Fase 1.

## 10. Limites respeitados

`[Executado]` Não houve Fase 1, coletor, acesso a fontes, teste externo,
navegação automatizada, servidor, abertura de porta, habilitação operacional,
alteração na SuiteViagem oficial, publicação de banco/credenciais/`.venv` ou
lançamento do produto.
