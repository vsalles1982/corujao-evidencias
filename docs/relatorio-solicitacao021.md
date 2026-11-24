# Relatório — Solicitação 021

Correções finais da Fase 0 do Corujão para aceitação técnica pelo Tech Lead.
Base documental: commit `79cf6b40aab48903c146d27954f18a26c9b3f4e7`.
Execução encerrada após esta entrega; nenhuma decisão normativa aprovada foi
reaberta e a Fase 1 **não** foi autorizada.

Convenção: `[Executado]` = comando rodado nesta sessão; `[Documental]` = decisão
normativa aplicada. Os registros das solicitações 019 e 020 foram preservados.

---

## 1. Resumo das correções

**Correção A — qualificação de sinais de indexação.** `register_indexing_signal()`
agora exige, no momento em que o sinal é recebido: identidade comprovada,
`equivalence_status = 'equivalent'` já declarado, fonte existente e com papel
compatível (referência → indexador; validadora → validador), metadados completos
da Solicitação 018 (`role`, `semantics`, `source_code`, `captured_at`,
`contract`) e observação não anterior a `first_seen_at`. Sinal não qualificado
não grava `indexed_at`, não grava `indexing_signal_json` e não produz lead time.
A primeira observação qualificada prevalece; sinal posterior não a substitui e
mudança posterior de equivalência não gera lead time retroativo.
`recompute_lead_time()` passou a validator a identidade efetiva no banco, em vez
de assumir `identity_valid=True`.

**Correção B — manifesto e hashes.** O JSON `docs/evidencia-verificacao-020.json`
não contém mais a entrada com o próprio SHA-256 (inconsistente: `050682c7…` no
JSON contra `b1c43a3a…` no manifesto). A tabela de hashes, que também trazia
valores hoje desatualizados, foi removida desse JSON e substituída por nota
explícita de correção. O manifesto antigo `docs/hashes-sha256-020.txt` foi
marcado como histórico e substituído. O novo `docs/hashes-sha256-021.txt` registra os hashes
finais dos bytes efetivamente publicados, incluindo o JSON concluído da
Solicitação 021 e este relatório, e documenta sua cobertura. Nenhum hash antigo
é apresentado como atual.

**Correção C — contrato documental.** Removida a afirmação residual de `gu_v2_`
para `path='unlinked'` na seção 5, item 3 de `docs/contrato-fase0.md`. A regra
final ficou inequívoca: Caminho A = `gq_v2_`, Caminho B = `gu_v2_`, local sem
vínculo = `ul_v1_`, exclusivamente em `observations`, sem
`quote_comparison_key`, sem comparação entre fontes e sem lead time. A seção 3
também passou a descrever a qualificação cumulativa e anterior.

**Correção D — normalização NFC.** Novo teste com texto acentuado em forma
composta (`econômica`, U+00F4) e decomposta (`econo` + U+0302 + `mica`),
comprovando payload canônico idêntico e mesmo hash `ul_v1_`. Nenhum vetor
normativo foi alterado.

## 2. Arquivos modificados e adicionados

`[Executado]` Modificados:

| Arquivo | Alteração |
|---|---|
| `src/corujao/temporal.py` | qualificação cumulativa, papel da fonte, identidade comprovada, bloqueio de lead time retroativo |
| `tests/test_fase0.py` | teste 09 corrigido; testes 13 a 18 acrescentados |
| `docs/contrato-fase0.md` | item 3 da seção 5 reescrito; seção 3 reforçada |
| `docs/evidencia-verificacao-020.json` | auto-hash e tabela de hashes desatualizada removidos; nota de correção |
| `docs/hashes-sha256-020.txt` | marcado como histórico/substituído |
| `docs/codigo-fase0/temporal.py` | cópia byte a byte do módulo final |
| `docs/codigo-fase0/test_fase0.py` | cópia byte a byte da suíte final |

`[Executado]` Adicionados em `docs/`:

- `evidencia-testes-021.txt` — saída integral da suíte;
- `evidencia-verificacao-021.json` — verificação final, sem auto-hash;
- `hashes-sha256-021.txt` — manifesto final;
- `relatorio-solicitacao021.md` — este relatório.

As duas cópias alteradas em `codigo-fase0/` foram comparadas por SHA-256 com os
arquivos locais de origem: **iguais byte a byte**. As oito cópias restantes
permaneceram inalteradas.

Nenhuma migração foi criada ou alterada: `0001` e `0002` permanecem com suas
datas, descrições e conteúdo originais. Não houve defeito comprovado que exigisse
toque na migração `0002`.

## 3. Resultado integral dos testes

`[Executado]` `.venv/bin/python -m unittest discover -s tests -v` — saída
integral em `docs/evidencia-testes-021.txt`:

```text
test_01_criacao_inicial_do_banco ... ok
test_02_bootstrap_sem_duplicacao ... ok
test_03_migracoes_rastreaveis ... ok
test_04_integridade_referencial_e_estrutural ... ok
test_05_unicidade_e_protecao_de_identidade ... ok
test_06_seis_vetores_de_hash ... ok
test_07_caminhos_a_e_b ... ok
test_08_separacao_generic_quote_e_identified_offer ... ok
test_09_first_seen_indexed_e_lead_time ... ok
test_10_fontes_estado_inicial_desabilitado ... ok
test_11_ul_v1_estabilidade_e_distincao ... ok
test_12_migracao_0002_dominio_sources ... ok
test_13_sinal_equivalencia_desconhecida_nao_qualifica ... ok
test_14_sinal_fonte_inexistente_rejeitado ... ok
test_15_sinal_fonte_sem_papel_rejeitado ... ok
test_16_sinal_valido_e_primeira_observacao ... ok
test_17_equivalencia_tardia_nao_gera_lead_time_retroativo ... ok
test_18_normalizacao_nfc_texto_acentuado ... ok

Ran 18 tests in 0.232s

OK
```

**18/18 aprovados.** Cobertura exigida pela Correção A:

| Teste | Caso |
|---|---|
| 09 | sinal válido qualifica; sinal posterior não substitui o primeiro |
| 13 | equivalência desconhecida rejeitada, sem `indexed_at` e sem lead time |
| 14 | fonte inexistente rejeitada |
| 15 | fonte sem papel de indexador/validador rejeitada |
| 16 | sinal válido aceito; primeira observação prevalece; lead time = 1800 s |
| 17 | equivalência posterior não gera lead time retroativo |

Correção D: teste 18 comprova que as duas formas NFC produzem o mesmo payload
canônico e o mesmo hash. Nenhum acesso a rede, navegador, porta, coletor ou
fonte externa.

## 4. Verificações SQLite

`[Executado]` Dados de `docs/evidencia-verificacao-021.json`, lidos do banco
real em `data/corujao.sqlite3` pela conexão de `corujao.db.connect`:

| Verificação | Valor |
|---|---|
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | `[]` |
| `PRAGMA journal_mode` | `wal` |
| `PRAGMA foreign_keys` | `1` |
| `PRAGMA busy_timeout` | `5000` ms |
| tabelas | 9 |
| índices | 5 |
| triggers | 17 |
| migrações registradas | `0001`, `0002` |
| `new_migrations` na verificação final | `[]` |
| schema efetivo (sha256) | `4b12034484ee51fa682c6ab141605770f10d3df1e04f2d994e7e1b64249231f0` |

DDL efetivo de `sources`: `CHECK (operational_enabled IN (0, 1))` presente e
`CHECK (operational_enabled = 0)` ausente.

## 5. Situação das fontes

`[Executado]` Nenhuma alteração:

| Código | `evaluation_status` | `operational_enabled` |
|---|---|---|
| `decolar` | `not_evaluated` | `0` |
| `google_flights` | `not_evaluated` | `0` |
| `latam` | `not_evaluated` | `0` |
| `turismocity` | `not_evaluated` | `0` |

Fontes desabilitadas e não avaliadas. Nenhuma foi habilitada, consultada ou
integrada. Bootstrap permanece com uma única linha; não foi reaplicado.

## 6. Confirmação dos vetores

`[Documental]` Os sete hashes normativos permanecem idênticos aos da Revisão 010
e da Solicitação 020, com seus prefixos:

| Finalidade | Hash |
|---|---|
| contexto (A) | `qctx_v2_37651064cce52afab439d8dae7a8a8e6b7134d6377cedcfb0ee22a6be667aa53` |
| cotação A | `gq_v2_dfaf7c87ccb96fa313eb1d2db5092fba0a63fcd3c0a1073f1a470aea05416f67` |
| cotação B | `gu_v2_a06da76bb5222722cd3d0f7143d746f55586dd63d6e19d9d0967545a8f795075` |
| chave de comparação | `qc_v2_99290a118887f0e242c4e9ed4a2cb687b4b9ce741ae78c968a6a0f55f599c512` |
| oferta identificada | `io_v1_01dda36b231079809c73147a7268918282a9d770def6368e9db9ec11ef6bd8c1` |
| chave de voo | `cf_v1_98ff10b1588997c5d0090dc77f3216f980b48432a1dc86dc7a4822bd5b50ce59` |
| local sem vínculo | `ul_v1_04a9fe3c0fb396d9d211492b3d15d43bab1fa68c00b8401c406934fd473c41b2` |

`test_06` e `test_11` revalidaram todos os vetores; `test_08` confirmou a
separação entre `generic_quotes`, `identified_offers` e `observations`.

## 7. Manifesto atualizado

`[Executado]` `docs/hashes-sha256-021.txt` foi gerado ao final, a partir dos
bytes finais publicados. Cobertura: **todos** os arquivos de `docs/`, incluindo
as dez cópias em `codigo-fase0/`, as evidências antigas e novas, os dois
relatórios de solicitação, o contrato, os vetores, o schema efetivo, este
relatório e o JSON `evidencia-verificacao-021.json`. O próprio manifesto não
contém seu hash, por definição. Hashes de referência:

| Arquivo | SHA-256 |
|---|---|
| `codigo-fase0/temporal.py` | `c5f8cbf02de43c2281af4a05fda1a65c4b44e3df5f3a3183afd8424202265967` |
| `codigo-fase0/test_fase0.py` | `60b9378d494498ca8d410a7e9e90fca33cdbfef87279ccc34324d4adf531b81a` |
| `contrato-fase0.md` | `b501a891ffaada099e3fcdce41a99df25441095b1460c2377fe7d0692f51d70a` |
| `evidencia-verificacao-020.json` | `1e26abcc9abf97a3a6e9f694663bc050158c8dc7d46c75a48b25524619bfffa1` |
| `evidencia-verificacao-021.json` | `c0ec8db91517a5f14af7b4b40fea0ccc774553af7e2254db9b009b3b4b149314` |
| `evidencia-testes-021.txt` | `8296a1e2ef6b62bd91f8531811999da581c28bf3e8ff5da688723367e985949a` |

Nenhum JSON de evidência contém o próprio hash. O manifesto `020` está marcado
como histórico e não deve ser usado como referência atual.

## 8. Commit publicado

`[Executado]` Publicação em `vsalles1982/corujao-evidencias`, ramo `main`, em
commit novo, sem `reset`, `clean`, `rebase` ou `force push`. O SHA do commit é
informado na resposta de entrega desta solicitação e pode ser confirmado por
`git log -1` no repositório. Nenhum banco de dados, credencial, segredo ou
`.venv` foi publicado.

## 9. Pendências

`[Documental]` Nenhuma pendência técnica da Solicitação 021 permanece. Restam
as pendências de escopo já registradas, todas dependentes de autorização
própria: Fase 1, coletores, integrações, interface, agendamento, alertas,
validação de promoções, fonte cambial aprovada, política de retenção
definitiva e avaliação operacional das fontes. A aceitação definitiva da Fase 0
continua sob responsabilidade do Tech Lead; esta entrega **não autoriza a
Fase 1** e a execução está encerrada, aguardando revisão.

## 10. Limites respeitados

`[Executado]` Não houve Fase 1, coletor, acesso a fontes, teste externo,
navegação automatizada, servidor, abertura de porta, habilitação operacional,
alteração na SuiteViagem oficial (congelada em
`ebab472772348222501c741c9559398e3e74b558`), publicação da suíte oficial,
publicação de banco/credenciais/`.venv` ou lançamento do produto.
