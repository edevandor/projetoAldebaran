# PLANS.md — Planos de Implementação

Este ficheiro regista os planos de implementação organizados por fase e
microciclo (X.Y.Z). Cada fase concluída pode ser arquivada para manter
o ficheiro leve.

---

## Fase 1 — Ingestão (Parser do XLSX Hierárquico) ✅

**Objetivo:** Implementar o módulo `src/ingestion/` para ler os XLSX de
mapas estatísticos de vendas e extrair dados tabulares limpos.

### MC-1.1 — Estrutura base do parser ✅

- `src/ingestion/parser.py` — máquina de estados (METADATA → ARTICLE_HEADER → COLUMN_HEADER → DATA → TOTAL)
- 10 testes, extração de 8 campos (produto, data_emissao, tipo_documento, numero_documento, protocolo, valor_total_venda, quantidade, unidade_medida)
- Validação em dados de exemplo: 149.129 linhas, 0 inválidas, 14 ficheiros

### MC-1.2 — Múltiplos ficheiros e batch ✅

- `src/ingestion/directory.py` — `ingest_directory()` varre, ordena, concatena com coluna `arquivo_origem`
- 5 testes (diretório vazio, concatenação, coluna origem, origens distintas, colunas do parser)

---

## Fase 2 — Validação e Padronização ✅

**Objetivo:** Padronizar os dados extraídos e validar contra regras de negócio.

### MC-2.1 — Padronização ✅

- `src/transformation/standardizer.py` — separa `codigo_produto`/`descricao_produto`, gera `id_venda` e `id_item_venda`
- 7 testes (código/descrição, ids, colunas originais, produto sem separador, output do parser)

### MC-2.2 — Validação ✅

- `src/validation/validator.py` — `ValidationReport` dataclass + `validate()` checa campos obrigatórios e duplicatas
- 11 testes (dados válidos, campos ausentes, duplicatas, summary, output real)

---

## Fase 3 — Consolidação e Analytics ✅

**Objetivo:** Remover duplicatas exatas e calcular KPIs do MVP.

### MC-3.1 — Consolidação ✅

- `src/consolidation/consolidator.py` — `consolidate(df)` remove duplicatas exatas (todas as colunas, exceto `arquivo_origem`)
- Validação real: 0 duplicatas removidas (dados já limpos — itens diferentes na mesma NF não são duplicatas)
- 5 testes

### MC-3.2 — Analytics (KPIs) ✅

- `src/analytics/kpis.py` — `compute_kpis(df)` calcula:
  - Faturamento total, qtd notas fiscais, total itens, ticket médio
  - Top produtos (valor e quantidade)
  - Vendas por mês
- 8 testes
- KPIs de exemplo: R$ 180,7M faturamento, 53.654 NFs, ticket médio R$ 3.367

---

## Fase 4 — Exportação e Auditoria ✅

**Objetivo:** Exportar dados e KPIs; registar execuções do pipeline.

### MC-4.1 — Exportação ✅

- `src/export/formatters.py` — `export_to_json(df, path)` e `export_to_markdown(kpis, path)`
- 9 testes (JSON: criação, conteúdo, data string, vazio, diretório; MD: criação, título, métricas, KPI mínimo)

### MC-4.2 — Auditoria ✅

- `src/audit/auditor.py` — `PipelineRun` dataclass + `criar_relatorio_pipeline(etapas)`
- 4 testes (criação, erros, resumo, integração com pipeline real)

### MC-4.3 — Orquestração e Refactor ✅

- `src/pipeline.py` — `run_pipeline(data_dir)` executa todas as etapas e retorna dados + KPIs + relatório
- Refactor: constantes de coluna no parser, suporte a .xls (xlrd) no directory, lambdas removidos do standardizer
- 4 testes de regressão (pipeline sintético, orquestração, etapas, export+audit integrados)

### Resumo Final

| Fase | Módulos | Testes |
|------|---------|--------|
| 1 — Ingestão | parser, directory | 15 |
| 2 — Transformação + Validação | standardizer, validator | 18 |
| 3 — Consolidação + Analytics | consolidator, kpis | 13 |
| 4 — Exportação + Auditoria | formatters, auditor, pipeline | 17 |
| **Total** | **12 módulos** | **63 ✅** |
