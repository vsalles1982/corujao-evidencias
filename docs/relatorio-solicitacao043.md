# Corujão — Precisão na classificação de `sqlite3.IntegrityError`

**Solicitação:** 043 · **Executor:** OpenCode / BigPickle · **Revisor:** Tech Lead  
**Modo:** somente leitura, análise técnica e proposta documental.

## Convenção de classificação

- **[Comprovado]** — obtido por leitura de arquivo local, metadados do esquema ou cálculo de hash nesta solicitação.
- **[Documental]** — registrado em relatório anterior ou em arquivo de sistema lido agora; não revalidado por execução nesta solicitação.
- **[Recomendação]** — ajuste proposto; não autoriza implementação e não altera decisões aprovadas.

---

## 1. Inconsistência na Solicitação 042

**[Documental]** A Solicitação 042, Seção 5 (`docs/relatorio-solicitacao042.md:151-171`), estabelece que, após `sqlite3.IntegrityError`, a releitura pela identidade natural que encontre uma linha idêntica, com hash canônico e `active=1`, confirma `reused=true`.

**[Recomendação]** Essa regra é insuficiente. A existência de uma linha correspondente não demonstra que a violação tenha sido causada pelo índice único esperado de `route_dates`. Um erro de `CHECK`, `FOREIGN KEY`, `NOT NULL`, chave primária ou outro índice único também produz `sqlite3.IntegrityError`; nenhum desses casos autoriza reutilização. Além disso, a linha encontrada pode ter sido inserida pela própria operação antes do erro, e não ser um registro preexistente.

**[Recomendação]** A regra corrigida exige prova dupla: identificação da causa da violação **e** confirmação de um registro preexistente, único e correspondente. Sem a primeira prova, a segunda não basta.

---

## 2. Evidências e arquivos consultados

| Fonte | Uso |
|---|---|
| `src/corujao/migrations.py:42-68` | DDL de `route_dates`, `CHECK`s, FKs e os dois índices únicos parciais |
| `docs/relatorio-solicitacao042.md:151-171` | regra de releitura que precisa de correção |
| `docs/relatorio-solicitacao042.md:179-188` | cenários T042-C03 a T042-C09 que permanecem vigentes, com acréscimos |
| `src/corujao/db.py:12-19` | conexão com `foreign_keys=ON`, WAL e `busy_timeout` |
| `src/corujao/identity.py:114-126` | cálculo do hash canônico `qctx_v2_` |
| `.venv/pyvenv.cfg:3-4` | Python 3.14.8 no ambiente local |
| `/usr/lib/python3.14/sqlite3/__main__.py:27-32` | uso local de `e.sqlite_errorname` em tratamento de erro |
| `/usr/lib/python3.14/sqlite3/dbapi2.py:27` | exposição dos símbolos do módulo `_sqlite3` |
| `/usr/include/sqlite3.h:483-499,4217-4239,563,570` | diferença entre código primário e código estendido; constantes de restrição |
| `_sqlite3.cpython-314-x86_64-linux-gnu.so` (símbolos lidos) | presença de `sqlite_errorcode`, `sqlite_errorname`, `sqlite3_errcode` e `sqlite3_extended_errcode` |
| `sqlite3 -readonly` em `data/corujao.sqlite3` | versão do SQLite, `index_list`, `index_info`, `table_info`, integridade e FK |

**[Comprovado]** A versão do SQLite informada pelo próprio banco é `3.54.0`. O banco consultado permanece com `integrity_check=ok` e `foreign_key_check` vazio.

**[Comprovado]** Foram lidos, mas não executados, testes, código de aplicação novo ou qualquer comando de escrita. Nenhuma violação de restrição foi provocada para observar mensagens de erro reais.

---

## 3. Índices e restrições efetivamente encontrados

### 3.1 Estrutura da tabela

**[Comprovado]** `PRAGMA table_info('route_dates')` e `migrations.py:42-58` mostram:

| Coluna | Tipo | Restrição |
|---|---|---|
| `id` | INTEGER | `PRIMARY KEY` (alias de rowid) |
| `route_id` | INTEGER | `NOT NULL`, `REFERENCES routes(id) ON DELETE RESTRICT` |
| `departure_date` | TEXT | `NOT NULL` |
| `return_date` | TEXT | anulável |
| `trip_type` | TEXT | `NOT NULL`, `CHECK (IN ('oneway','roundtrip'))` |
| `adults` | INTEGER | `NOT NULL`, padrão `1`, `CHECK (>= 1)` |
| `children` | INTEGER | `NOT NULL`, padrão `0`, `CHECK (>= 0)` |
| `infants` | INTEGER | `NOT NULL`, padrão `0`, `CHECK (>= 0)` |
| `cabin` | TEXT | `NOT NULL`, padrão `'economy'` |
| `query_context_hash` | TEXT | anulável |
| `active` | INTEGER | `NOT NULL`, padrão `1`, `CHECK (IN (0,1))` |
| `created_at` | TEXT | `NOT NULL` |

**[Comprovado]** Há ainda os `CHECK` de coerência (`oneway` com `return_date IS NULL`, `roundtrip` com `return_date IS NOT NULL`) e o `CHECK (return_date IS NULL OR departure_date <= return_date)`, além da própria tabela ser `STRICT`.

### 3.2 Índices únicos

**[Comprovado]** `PRAGMA index_list('route_dates')` retornou exatamente dois índices, ambos únicos (`unique=1`) e parciais (`partial=1`):

```sql
CREATE UNIQUE INDEX uq_route_date_oneway
  ON route_dates(route_id, departure_date, adults, children, infants, cabin,
                 COALESCE(query_context_hash, ''))
  WHERE return_date IS NULL;

CREATE UNIQUE INDEX uq_route_date_roundtrip
  ON route_dates(route_id, departure_date, return_date, adults, children,
                 infants, cabin, COALESCE(query_context_hash, ''))
  WHERE return_date IS NOT NULL;
```

**[Comprovado]** `PRAGMA index_info` confirma as colunas:

- `uq_route_date_oneway`: `route_id`, `departure_date`, `adults`, `children`, `infants`, `cabin` e uma expressão (cid `-2`, o `COALESCE`); o predicado parcial é `return_date IS NULL`.
- `uq_route_date_roundtrip`: `route_id`, `departure_date`, `return_date`, `adults`, `children`, `infants`, `cabin` e a mesma expressão; o predicado parcial é `return_date IS NOT NULL`.

**[Comprovado]** O `id INTEGER PRIMARY KEY` também é uma restrição de unicidade implícita, embora não apareça na lista de índices criados explicitamente.

**[Recomendação]** O índice esperado para a identidade da intenção depende do `trip_type`: `uq_route_date_oneway` para `oneway`, `uq_route_date_roundtrip` para `roundtrip`. Qualquer outra restrição violada — inclusive o índice oposto, a chave primária, um `CHECK`, uma FK ou um `NOT NULL` — não é “conflito de unicidade esperado”.

---

## 4. Capacidade de identificar a causa do `IntegrityError`

### 4.1 Atributos disponíveis

**[Comprovado]** O ambiente usa Python 3.14.8. O arquivo `/usr/lib/python3.14/sqlite3/__main__.py:27-32` lê `e.sqlite_errorname` ao tratar `sqlite3.Error`, e os símbolos `sqlite_errorcode` e `sqlite_errorname` existem no módulo `_sqlite3` local. As constantes estendidas `SQLITE_CONSTRAINT_CHECK`, `SQLITE_CONSTRAINT_FOREIGNKEY`, `SQLITE_CONSTRAINT_NOTNULL`, `SQLITE_CONSTRAINT_PRIMARYKEY`, `SQLITE_CONSTRAINT_UNIQUE`, entre outras, também estão presentes no módulo.

**[Documental]** O cabeçalho local do SQLite (`/usr/include/sqlite3.h:483-499`) explica que, na configuração padrão, as rotinas retornam códigos primários; os códigos estendidos fornecem detalhamento e podem ser obtidos por `sqlite3_extended_errcode()` ou habilitados por conexão. O mesmo cabeçalho (`4217-4239`) define `sqlite3_errcode()` e `sqlite3_extended_errcode()` como interfaces distintas.

**[Comprovado]** O binário `_sqlite3` referencia tanto `sqlite3_errcode` quanto `sqlite3_extended_errcode`. Por leitura isolada não é possível demonstrar qual das duas funções alimenta `sqlite_errorcode` na exceção.

**[Recomendação]** Não se deve presumir que `sqlite_errorcode` traga o código estendido. Se trouxer apenas o código primário, todos os casos acima aparecerão como `SQLITE_CONSTRAINT` (19), indistintos entre si.

### 4.2 Mensagem textual

**[Recomendação]** A mensagem de `str(exc)` pode conter indícios como “UNIQUE constraint failed”, “CHECK constraint failed” ou “FOREIGN KEY constraint failed”, mas nenhum desses textos foi observado por execução nesta solicitação. Não há garantia documentada, nos arquivos lidos, de que a mensagem identifique **qual dos dois índices parciais** foi violado. Analisar a mensagem como prova definitiva seria frágil e dependente de versão.

### 4.3 Conclusão da análise

**[Recomendação]** Com o mecanismo atualmente proposto — exceção Python padrão mais releitura — **não é possível afirmar, de forma inequívoca, qual restrição foi violada**. Mesmo que o código estendido esteja disponível, ele distingue a categoria (`CHECK`, `FOREIGNKEY`, `UNIQUE`, `NOTNULL`, `PRIMARYKEY`), mas os arquivos lidos não demonstram que ele identifique o índice parcial específico de `route_dates`.

**[Recomendação]** Diante dessa limitação, adota-se o comportamento conservador exigido pela Solicitação 043: **sem identificação inequívoca da causa, não se confirma `reused=true` após `IntegrityError`**. O desfecho é `integrity_violation` com rollback integral.

---

## 5. Influência de `BEGIN IMMEDIATE` e da releitura na mesma transação

**[Comprovado]** `db.py:12-19` configura `foreign_keys=ON`, WAL e `busy_timeout`; a Solicitação 041 introduziu `BEGIN IMMEDIATE` para a operação de intenção de busca.

**[Recomendação]** `BEGIN IMMEDIATE` reduz a possibilidade de que outra conexão modifique `route_dates` entre a leitura e a escrita, mas **não**:

1. identifica a restrição violada;
2. impede que a própria operação tenha inserido uma linha antes do erro;
3. transforma a releitura em prova de que o registro é preexistente;
4. elimina a possibilidade de erro de `CHECK`, FK, `NOT NULL`, chave primária ou índice diverso.

**[Recomendação]** Para excluir a hipótese de autoinserção, a operação deve manter um registro em memória dos `id`s que inseriu na transação corrente (ou usar estado equivalente de savepoint). Se a linha encontrada na releitura tiver `id` pertencente a essa coleção, ela **não** é preexistente: o desfecho é `integrity_violation` com rollback, nunca `reused=true`.

**[Recomendação]** A releitura continua sendo necessária para detectar registros legados ambíguos, contexts distintos e registros inativos, mas passa a ser apenas uma das duas provas exigidas.

---

## 6. Regra corrigida de classificação

| Situação | Classificação | Desfecho |
|---|---|---|
| Causa identificada como conflito do índice único esperado **e** releitura encontra exatamente um registro preexistente, idêntico, com hash canônico e `active=1` | conflito de unicidade esperado | `reused=true`; nenhuma escrita adicional |
| Causa identificada como `CHECK`, `FOREIGN KEY`, `NOT NULL`, chave primária ou outro índice | conflito não explicado para a identidade | `integrity_violation`; rollback; sem confirmação |
| Causa não identificável com segurança | conflito não explicado | `integrity_violation`; rollback; sem confirmação |
| Releitura não encontra registro correspondente | conflito não explicado | `integrity_violation`; rollback; sem confirmação |
| Releitura encontra mais de um registro com o mesmo hash canônico | divergência inesperada | `integrity_violation` / `unexpected_route_date_state`; rollback |
| Registro encontrado tem `id` inserido pela própria operação | autoinserção | `integrity_violation`; rollback; sem reutilização |
| Identidade natural coincide, mas hash é `NULL` ou `''` | registro legado ambíguo | `identity_mismatch`; rollback, conforme 042 |
| Hash não vazio e diferente, sem `IntegrityError` | contexto distinto | nova linha legítima, conforme 042 |
| Hash não vazio e diferente, após `IntegrityError` | conflito não explicado | `integrity_violation`; rollback |
| Registro idêntico com `active=0` | registro inativo | `route_date_inactive`; sem reativação |

**[Recomendação]** A prova de causa e a prova de preexistência são cumulativas. Não basta que uma linha correspondente exista: é preciso demonstrar que o erro veio do índice esperado e que a linha não foi criada pela própria operação.

**[Recomendação]** Se uma futura implementação não conseguir identificar a restrição de forma inequívoca com o mecanismo disponível, ela deverá adotar o ramo conservador da tabela para todo `IntegrityError`, sem exceção.

---

## 7. Cenários sintéticos propostos

**[Recomendação]** Nenhum cenário abaixo foi executado. Todos devem usar banco temporário criado pela sequência `0001 → 0002 → 0003`, sem apontar para `data/corujao.sqlite3` ou para o backup.

| Caso | Preparação sintética | Resultado esperado |
|---|---|---|
| **T043-C01** | conflito no índice único esperado, com identificação inequívoca da causa e um registro preexistente correspondente e ativo | `reused=true`; nenhuma escrita; confirmação com `id` preexistente |
| **T043-C02** | violação de `CHECK` (por exemplo, `adults=0` ou `trip_type` incompatível com `return_date`), com linha correspondente também presente | `integrity_violation`; rollback; nenhuma reutilização; nenhuma confirmação |
| **T043-C03** | violação de `FOREIGN KEY` em `route_id`, com linha correspondente também presente | `integrity_violation`; rollback; nenhuma reutilização |
| **T043-C04** | violação de outro índice único, por exemplo duplicação de `id INTEGER PRIMARY KEY` | `integrity_violation`; rollback; nenhuma reutilização |
| **T043-C05** | erro de integridade cuja causa não possa ser identificada | `integrity_violation`; rollback; nenhuma reutilização |
| **T043-C06** | `IntegrityError` seguido de releitura sem registro correspondente | `integrity_violation`; rollback; nenhuma confirmação |
| **T043-C07** | a própria operação insere a linha e, em seguida, provoca novo `IntegrityError`; releitura encontra essa linha | `integrity_violation`; rollback; `reused=false`, mesmo com hash idêntico e `active=1` |
| **T043-C08** | releitura encontra exatamente um registro preexistente, correspondente, ativo, com causa identificada como o índice esperado | `reused=true`; mesmos `id`, `created_at`, `updated_at`; zero escritas |
| **T043-C09** | registro legado com `NULL` e outro com `''` | casos separados; `identity_mismatch`; rollback, conforme T042-C04a e T042-C04b |
| **T043-C10** | registro correspondente com `active=0` | `route_date_inactive`; sem reativação, conforme T042-C07 |

**[Recomendação]** As evidências futuras devem registrar, para cada caso: atributos da exceção obtidos, mensagem literal, índice ou restrição identificada, ids inseridos na transação, linhas retornadas pela releitura e desfecho da transação.

---

## 8. Limitações técnicas

1. **[Recomendação]** Código primário `SQLITE_CONSTRAINT` não distingue CHECK, FK, NOT NULL, chave primária ou unicidade.
2. **[Recomendação]** Não foi comprovado por leitura que `sqlite_errorcode` exponha o código estendido na exceção Python local.
3. **[Recomendação]** Mesmo o código estendido não demonstra, nos arquivos consultados, que identifica qual dos dois índices parciais foi violado.
4. **[Recomendação]** Texto de mensagem não é contrato estável e não deve ser a única base para autorizar reutilização.
5. **[Recomendação]** Releitura na mesma transação não prova preexistência; exige controle explícito dos ids inseridos pela operação.
6. **[Recomendação]** `BEGIN IMMEDIATE` serializa escritores, mas não corrige nenhuma das limitações acima.
7. **[Recomendação]** Como consequência, a identificação inequívoca pode não ser alcançável com o mecanismo proposto; nesse caso, a regra conservadora se aplica integralmente.

---

## 9. Declaração explícita do que não foi executado

Nesta Solicitação 043 **não foram executadas**:

- implementação de código, comando, módulo ou mecanismo de diagnóstico;
- execução dos cenários T043-C01 a T043-C10 ou de qualquer outro teste;
- provocação deliberada de violação de restrição, inclusive em banco temporário;
- SQL de escrita, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP` ou `ALTER`;
- criação ou execução de migration;
- alteração do banco real, do backup, de `identity.py`, `migrations.py`, `db.py`, `docs/relatorio-solicitacao041.md` ou `docs/relatorio-solicitacao042.md`;
- acesso a LATAM, Decolar, Turismocity, Google Flights ou qualquer fonte externa;
- habilitação de fonte ou inicialização de serviço, coletor, navegador, porta ou agendador;
- criação de commit, branch, tag, PR, push ou publicação;
- modificação da SuiteViagem oficial;
- qualquer operação da Fase 1.

**[Comprovado]** A única escrita nesta solicitação foi a criação de `docs/relatorio-solicitacao043.md`. As demais operações foram leitura de arquivos, leitura de cabeçalhos e símbolos locais, consultas SQLite **somente leitura**, cálculo de hashes e verificação de estado de repositórios.

---

## 10. Hashes e estado observado

**[Comprovado]** Hashes calculados nesta solicitação:

| Arquivo | SHA-256 |
|---|---|
| `docs/relatorio-solicitacao042.md` | `636f4de3b07d95ad292482b8ad58312f8811dedf37f9513af3619cbe7831c002` |
| `docs/relatorio-solicitacao041.md` | `2edfff1dca6a62f647c2f43bfbc027af3ef0ba7c40044d8ca7711f2ba77b1223` |
| `src/corujao/identity.py` | `987ddcaa82d9c8c3a96ff5c2c7fea71db0f1e534ceeaa07db820023baad3ae56` |
| `src/corujao/migrations.py` | `febde41dc610c74feeb162eeb6264df905505403ab76618d6bd5b86639cbb7f0` |
| `src/corujao/db.py` | `77d7024401543303806307653133272696ce6730ff9573d56d94fd9241cbce39` |
| `data/corujao.sqlite3` | `f3b5ad4826486be334d1bf2713dc5d77c926d5eaa428b212a67e0d3b9b12c062` |
| `data/backup-pre-0003-20261125T025405Z.sqlite3` | `45914b4a5b525e1d20c4c1e7148732bb9faf71d9cbec21381de027de8213308d` |

**[Comprovado]** Estado observado:

| Item | Valor |
|---|---|
| Versão do SQLite | `3.54.0` |
| Versão do Python no `.venv` | `3.14.8` |
| Migrações registradas | `0001`, `0002`, `0003` |
| `routes` / `route_dates` | 0 / 0 linhas |
| `source_runs` / `evidence` | 0 / 0 linhas |
| `integrity_check` / `foreign_key_check` | `ok` / vazio |
| Índices em `route_dates` | `uq_route_date_oneway` e `uq_route_date_roundtrip`, ambos únicos e parciais |
| Fontes | quatro em `not_evaluated` e `operational_enabled=0` |
| Repositório Git local | ausente; nenhum commit, branch, tag, push ou PR |
| Clone de evidências | `main...origin/main`, limpo |
| SuiteViagem oficial | `freeze/web-v3.7.2-champion`, limpa |

**[Comprovado]** O SHA-256 deste próprio relatório é informado na mensagem de entrega, para evitar autorreferência no conteúdo do arquivo.

---

**Solicitação 043 encerrada.** Os relatórios 041 e 042 foram preservados integralmente. Nenhuma implementação ou etapa operacional foi iniciada. Aguardando revisão do Tech Lead.
