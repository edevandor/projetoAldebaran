# Consultas sobre a base publicada

Depois de `aldebaran run`, o histórico fica em
`data/processed/vendas_consolidadas.parquet`, consultável em SQL local. A
tabela é exposta como `vendas`.

```bash
aldebaran query "SELECT COUNT(*) FROM vendas"
aldebaran query --listar          # consultas prontas
aldebaran query sazonalidade --csv > sazonalidade.csv
```

Também é possível consultar direto do DuckDB, Polars ou pandas, sem depender
da CLI:

```sql
SELECT * FROM read_parquet('data/processed/vendas_consolidadas.parquet');
```

## Consultas prontas

### `cobertura` — o que existe na base

Período coberto, volume e registros sem data, quebrados por sistema de origem.
É a primeira consulta a rodar depois de uma carga: mostra se o dado chegou como
esperado e se o histórico atravessa a troca de ERP.

```text
sistema_origem primeira_venda ultima_venda  itens  notas  itens_sem_data
         ATUAL     2025-01-04   2026-06-24    277    144             0.0
        LEGADO     2002-01-22   2022-12-23    256    105             0.0
         TOTAL     2002-01-22   2026-06-24    533    249             0.0
```

### `procedencia` — quanto do histórico é leitura e quanto é inferência

Separa o faturamento por `confianca_data`. As datas do sistema legado são
reconstruídas a partir do CI e chegam marcadas como `Inferida`; as do sistema
atual são lidas do relatório. Qualquer análise de série temporal sobre o
período antigo deve considerar isso.

### `sazonalidade` — faturamento mês a mês

```sql
SELECT date_trunc('month', data_emissao) AS mes,
       COUNT(DISTINCT id_venda)          AS notas,
       SUM(valor_total_venda)            AS faturamento
FROM vendas
WHERE data_emissao IS NOT NULL
GROUP BY mes
ORDER BY mes
```

A data é tipada como temporal no Parquet, então `date_trunc` e comparações com
`DATE '...'` funcionam sem conversão.

### `top-produtos` — concentração de faturamento

Ranking por faturamento e volume. Útil para separar o que vende muito em
quantidade do que sustenta a receita.

### `responsaveis` — desempenho por vendedor

Notas, faturamento e ticket médio por responsável — a informação que o formato
de origem expressava apenas pela posição da linha no relatório.

### `itens-por-nota` — a granularidade do dado

Distribuição de quantos itens compõem cada venda. Deixa explícito por que a
unicidade é validada em `id_item_venda` e não em `id_venda`.

## Padrões úteis

**Contagem de vendas** — sempre por `id_venda` distinto, nunca por linhas:

```sql
SELECT COUNT(DISTINCT id_venda) AS vendas, COUNT(*) AS itens FROM vendas;
```

**Recuperar os componentes de uma chave** — as chaves são reversíveis:

```sql
SELECT id_item_venda,
       split_part(id_item_venda, '|', 1) AS documento,
       split_part(id_item_venda, '|', 2) AS data,
       split_part(id_item_venda, '|', 3) AS protocolo
FROM vendas LIMIT 5;
```

**Isolar os registros sem data** — preservados de propósito, não descartados:

```sql
SELECT COUNT(*) FROM vendas WHERE data_emissao IS NULL;
```

**Rastrear a origem de uma linha** — a linhagem acompanha o dado:

```sql
SELECT arquivo_origem, sistema_origem, COUNT(*) AS linhas
FROM vendas GROUP BY 1, 2 ORDER BY 3 DESC;
```

**Analisar só o que tem data lida** — exclui o período reconstruído:

```sql
SELECT * FROM vendas WHERE confianca_data = 'Registrada';
```
