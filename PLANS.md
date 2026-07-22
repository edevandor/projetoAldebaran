# PLANS.md — Histórico de implementação

Registro das fases concluídas, por microciclo. Serve como rastro do que foi
construído e em que ordem; as decisões estão em `DECISIONS.md`.

---

## Fase 1 — Ingestão ✅

Leitura dos mapas estatísticos de vendas em XLSX.

- `ingestion/parser.py` — máquina de estados de cinco estados
  (METADATA → ARTICLE_HEADER → COLUMN_HEADER → DATA → TOTAL), extraindo 8
  campos por linha de venda.
- `ingestion/directory.py` — `ingest_directory()` varre, ordena e concatena
  múltiplos arquivos, marcando a origem de cada linha.
- Validação sobre os dados de origem: 149.129 linhas em 14 arquivos, 0
  inválidas.

## Fase 2 — Padronização e validação ✅

- `transformation/standardizer.py` — separação de código e descrição do
  produto, geração de `id_venda` e `id_item_venda`.
- `validation/validator.py` — `ValidationReport` com campos obrigatórios e
  unicidade.

## Fase 3 — Consolidação e analytics ✅

- `consolidation/consolidator.py` — remoção de duplicatas exatas entre
  períodos, ignorando `arquivo_origem`.
- `analytics/kpis.py` — faturamento, notas fiscais, itens, ticket médio,
  ranking de produtos e série mensal.

## Fase 4 — Exportação e auditoria ✅

- `export/formatters.py` — saídas em JSON e Markdown.
- `audit/auditor.py` — `PipelineRun` com etapas, duração e erros.
- `pipeline.py` — orquestração das etapas.

## Fase 5 — Sistema legado (2002–2022) ✅

Leitura dos relatórios de largura fixa do ERP anterior.

- `ingestion/parser_rel.py` — relatório sintético, totais acumulados por item.
- `ingestion/parser_rel_analitico.py` — relatório analítico, com
  desambiguação do ano de 2 dígitos pela sequência de CI.
- `ingestion/parser_rel_compras.py` — reconstrução cronológica das datas
  corrompidas a partir do CI, com nível de confiança por registro.

## Fase 6 — Base consultável e verificabilidade pública ✅

Transformação da saída em base analítica e do repositório em algo executável
por quem não tem os dados de origem.

- `export/schema.py` — schema canônico único para Parquet e CSV (D-008).
- Chaves de negócio com separador explícito e reversíveis (D-007).
- Unicidade validada no item, não na venda (D-009).
- Datas ausentes como aviso, preservando a venda (D-012).
- `query/` — consulta SQL local sobre o Parquet via DuckDB (D-011).
- `demo/` — geração de dados sintéticos nos formatos de origem, incluindo os
  `.rel` de largura fixa (D-010).
- `cli.py` — comandos `demo`, `run` e `query`.
- Validação e auditoria integradas ao pipeline, com `execucao.json` por
  execução.
- CI com lint, suíte completa em duas versões de Python e teste end-to-end.

**Resultado:** 141 testes.

## Fase 7 — Histórico unificado e correção das regras de negócio ✅

Auditoria do projeto contra o que a documentação prometia, e correção do que
não se sustentava.

- `ingestion/legado.py` — reconhecimento do tipo de cada `.rel` e ingestão do
  analítico de vendas no pipeline; o histórico publicado passou a cobrir de
  2002 a 2026 (D-017).
- `sistema_origem` e `confianca_data` no schema: data lida e data inferida
  deixam de se confundir na base publicada.
- `resolve_versoes` — período reexportado deixa de contar faturamento em
  dobro (D-014).
- Colisão de chave entre registros sem data passa a ser desambiguada em vez de
  fundir duas vendas (D-015).
- Ano reconstruído validado contra o período declarado no cabeçalho; um valor
  corrompido deixa de contaminar a série (D-016).
- Testes tautológicos substituídos por comparação com gabarito, verificada por
  mutação.
- Caminho `.xls` deixou de descartar silenciosamente linhas sem data e saiu de
  0% para cobertura efetiva.
- Ordem das etapas corrigida: a validação passou a rodar depois da
  consolidação.
- KPIs passaram a fechar: a soma da série mensal mais o residual sem data dá o
  faturamento total.
- `ingestion/rel_comum.py` — conversões e filtros que estavam triplicados nos
  parsers do legado.

**Resultado:** 181 testes, 93% de cobertura.

---

## Fase 8 — Contrato operacional e rastreabilidade forte ✅

- Dinheiro canônico em centavos inteiros, convertido para reais apenas na view
  SQL (D-018).
- Registros inválidos isolados em quarentena, com status parcial e preservação
  dos válidos (D-019).
- Precedência de versões por cobertura; empates recentes colocam toda a
  identidade em quarentena, sem ressuscitar versão antiga (D-014).
- `id_execucao` comum ao Parquet e à auditoria, fingerprints SHA-256, versão do
  schema e histórico por execução (D-020).
- Publicação preparada em staging para preservar o Parquet anterior diante de
  falhas tardias (D-020).
- Catálogo público neutralizado para não vincular o caso a um setor específico.

---

## Próximos passos

- Publicação do histórico de compras em base própria.
- Análise de sazonalidade sobre o período completo.
- Projeções e análise de cenários.
