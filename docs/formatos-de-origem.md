# Formatos de origem

Referência técnica dos formatos exportados pelos dois ERPs. Este documento
existe porque nenhum dos formatos tem especificação publicada: o layout foi
reconstruído por observação dos arquivos reais e está codificado nos parsers.

---

## XLSX hierárquico — ERP atual

Relatório *Mapa Estatístico de Vendas*, exportado como planilha, mas
estruturado como relatório de impressão.

### Tipos de linha

| Tipo | Como é reconhecida | Tratamento |
|------|-------------------|-----------|
| Metadados | Primeiras linhas: empresa, extração, página | Ignorada |
| Contexto de responsável | Coluna A começa com `Responsável:` | Atualiza o vendedor corrente |
| Contexto de artigo | Coluna A começa com `Artigo:` | Atualiza a categoria corrente |
| Cabeçalho de colunas | Coluna A igual a `Produto` | Ignorada |
| Venda | Coluna A preenchida, sem prefixo conhecido | Extraída, com contexto herdado |
| Subtotal | Coluna A começa com `Total:` | Ignorada |

A detecção dos prefixos é insensível a maiúsculas e tolera ausência de acentos
(`Responsável:` e `Responsavel:` são equivalentes), porque a grafia varia entre
arquivos.

### Mapeamento de colunas

| Coluna | Índice (0-based) | Campo |
|--------|-----------------|-------|
| A | 0 | `produto` (código + ` - ` + descrição) |
| D | 3 | estoque (ignorado) |
| F | 5 | `unidade_medida` |
| G | 6 | `quantidade` |
| H | 7 | `data_emissao` |
| I | 8 | `protocolo` |
| J | 9 | `numero_documento` (NF Nº) |
| N | 13 | `valor_total_venda` |

O arquivo tem 17 colunas; as demais não são aproveitadas.

### Armadilhas

- O subtotal por artigo tem a mesma forma de uma linha de venda em algumas
  exportações: somar sem filtrar conta o faturamento em dobro.
- O vendedor e a categoria não são colunas. Perdê-los na leitura significa
  perder a análise por responsável e por linha de produto.
- Vendas sem responsável atribuído existem no ERP e são preservadas como valor
  vazio.

---

## `.rel` de largura fixa — ERP legado (2002–2022)

Texto puro, 132 colunas por linha, codificação **latin-1**, números no padrão
brasileiro (`1.234,56`), cabeçalho de página repetido a cada bloco.

Linhas ignoradas pelos parsers: separadores (`=`, `-`), cabeçalhos de página
(`01-EMPRESA`, `SISTEMA`, `Periodo:`, `Mapa Estatistico`, `Almox..:`),
cabeçalho de colunas (`Item  Artigo`) e totais (`    Total`, `Total Movto`,
`Tipo Movto`).

### Variante 1 — Vendas, sintético

Totais acumulados por item no período. **Não contém venda individual**: não há
data, nota fiscal nem vendedor.

| Posição | Campo |
|---------|-------|
| 0–6 | código do item |
| 6–54 | descrição |
| 54–63 | quantidade em estoque |
| 63–67 | unidade de medida |
| 67–84 | quantidade vendida |
| 84–97 | total de custo |
| 97–110 | total de compra (valor de venda) |
| 110–122 | total líquido |
| 122–132 | margem percentual |

O campo de total líquido usa 12 caracteres para absorver o dígito que
extravasa do layout de 132 colunas quando o valor é grande.

### Variante 2 — Vendas, analítico

Uma linha por item de venda. O CI (Controle Interno) cumpre o papel de
identificador da venda, no lugar da nota fiscal.

| Posição | Campo |
|---------|-------|
| 0–6 | código do item |
| 6–66 | descrição |
| 66–71 | quantidade em estoque |
| 71–74 | unidade de medida |
| 74–80 | preenchimento |
| 80–92 | quantidade |
| 92–102 | data de saída (`dd/mm/aa`) |
| 102–116 | CI |
| 116–132 | total do item |

**O problema do ano com 2 dígitos.** `02` pode ser 2002; ao longo de vinte
anos, a sequência impressa regride ciclicamente. A desambiguação usa o CI: ele
é sequencial e só cresce, então ordenar por CI ordena por tempo. O parser
percorre os registros em ordem de CI e impede que o ano retroceda.

Como a série nunca desce, um ano impresso corrompido para mais contaminaria
todos os registros seguintes. Por isso o ano candidato é validado contra o
período declarado no cabeçalho: o que estiver fora é descartado em favor do
último ano válido e o registro fica marcado como `ano_suspeito`.

### Variante 3 — Compras, analítico

Mesmo layout da variante 2, com as datas corrompidas.

**O problema.** O ano impresso é `20` para a maior parte dos registros,
independentemente do período real, e parte das entradas traz a sentinela
`01/01/19` — o valor que o sistema gravava quando não tinha a data.

**A reconstrução.** O CI é o único eixo cronológico confiável:

1. os itens são agrupados por CI, e cada grupo recebe a data modal das suas
   linhas;
2. o período coberto é lido do próprio cabeçalho do relatório
   (`Periodo: 01/01/2005 a 31/12/2022`);
3. os CIs são distribuídos linearmente dentro desse período, cada ano
   recebendo uma fatia proporcional do intervalo de CI;
4. o último ciclo é ancorado no ano final do período, e a série é percorrida
   para trás.

**A premissa, declarada.** O passo 3 assume volume de CIs aproximadamente
constante ao longo dos anos. Numa operação que cresceu ou encolheu muito, os
anos intermediários saem deslocados. É estimativa, não medição.

Para CIs cuja data modal é a sentinela, o dia e o mês são descartados e apenas
o ano inferido é aproveitado.

**A declaração de confiança.** Cada registro reconstruído carrega:

| Nível | Critério |
|-------|----------|
| `Alta` | O ano impresso coincide com o ano inferido pelo CI |
| `Media` | Divergência, ou data modal minoritária dentro do grupo |
| `Baixa` | A data modal do grupo é a sentinela `01/01/19` |

`Alta` significa **concordância entre a data impressa e a inferida**, não
certeza sobre a data real. Como o ano impresso é majoritariamente `20`, na
prática só os registros atribuídos a 2020 alcançam esse nível.

A data impressa original é preservada em `data_original`, lado a lado com a
reconstruída. A inferência nunca é apresentada como dado de origem.

---

## Reprodução dos formatos

O módulo `src/demo/gerador_rel.py` gera arquivos `.rel` sintéticos com este
mesmo layout — 132 colunas, latin-1, números em formato brasileiro, cabeçalhos
repetidos e a sentinela de data — e `src/demo/gerador_xlsx.py` gera o XLSX
hierárquico.

É o que permite executar e testar os parsers do legado sem os arquivos
originais:

```bash
aldebaran demo
```
