# PROJECT_SPEC.md — Especificação funcional

## Visão geral

Pipeline de consolidação de histórico comercial a partir de relatórios
exportados por ERP, sem acesso ao banco de dados de origem. Lê os formatos de
relatório como eles são, aplica as regras de negócio da operação e publica uma
base consultável.

## Objetivo

Tornar analisável um histórico comercial que existia apenas como relatório —
cerca de 25 anos distribuídos entre dois sistemas e dois formatos incompatíveis
com ferramentas de análise.

### Princípios

- Os arquivos de origem nunca são alterados.
- Todo indicador publicado deve ser rastreável até a execução que o produziu.
- As regras de negócio ficam centralizadas, não espalhadas pelos módulos.
- O que é inferido é declarado como inferido.
- A base publicada é a fonte oficial para análise.

## Escopo

**Dentro do escopo**

- Leitura de XLSX e XLS no formato hierárquico do ERP atual.
- Leitura dos três formatos `.rel` de largura fixa do ERP legado (2002–2022):
  vendas sintético, vendas analítico e compras analítico.
- Padronização, validação, consolidação e cálculo de KPIs.
- Publicação em Parquet tipado e consulta SQL local.
- Exportação opcional em CSV padronizado.
- Auditoria por execução.

**Fora do escopo**

- Conexão direta ao banco do ERP ou réplica de leitura.
- Escrita ou importação de volta no ERP.
- Hospedagem ou dependência de uma ferramenta específica de visualização.

## Fontes de dados

### XLSX hierárquico (ERP atual)

Relatório de impressão convertido em planilha, com três níveis:

1. **Metadados** — empresa, data de extração, página, responsável.
2. **Blocos**, que se repetem:
   - `Responsável: NOME` — contexto de vendedor;
   - `Artigo: NOME` — contexto de categoria;
   - linha de cabeçalho de colunas;
   - linhas de venda;
   - `Total: ...` — subtotal.
3. 17 colunas originais; 10 campos aproveitados no modelo de dados.

O vendedor e a categoria são expressos por posição, não por coluna: o parser
precisa herdá-los do bloco corrente.

### `.rel` de largura fixa (ERP legado, 2002–2022)

Texto de 132 colunas, codificação latin-1, números em formato brasileiro e
cabeçalho de página repetido a cada bloco. Três variantes:

| Variante | Conteúdo | Particularidade |
|----------|----------|----------------|
| Vendas sintético | Totais acumulados por item no período | Sem data, nota ou vendedor |
| Vendas analítico | Uma linha por item de venda | Ano com 2 dígitos, desambiguado pela sequência de CI |
| Compras analítico | Uma linha por item de entrada | Datas corrompidas; ano reconstruído a partir do CI |

## Modelo de dados

O contrato da saída está definido em `src/export/schema.py` e é compartilhado
por Parquet e CSV.

| Campo | Tipo | Obrigatório | Origem |
|-------|------|-------------|--------|
| `id_execucao` | texto | Sim | Identificador UTC único da execução |
| `id_item_venda` | texto | Sim | `id_venda` + protocolo — chave primária |
| `id_venda` | texto | Sim | sistema + `numero_documento` + `data_emissao` |
| `data_emissao` | data | Não | Coluna H do XLSX; ausência é sinalizada |
| `tipo_documento` | texto | Sim | Prefixo de `numero_documento` (série) |
| `numero_documento` | texto | Sim | Coluna J (NF Nº) |
| `protocolo` | texto | Não | Coluna I; ausência usa identidade conservadora |
| `codigo_produto` | texto | Não | Coluna A, antes do separador ` - ` |
| `descricao_produto` | texto | Sim | Coluna A, após o separador ` - ` |
| `quantidade` | decimal | Não | Coluna G |
| `unidade_medida` | texto | Não | Coluna F |
| `valor_total_venda_centavos` | inteiro | Sim | Coluna N, convertida para centavos |
| `responsavel` | texto | Não | Linha `Responsável: NOME` do bloco |
| `artigo` | texto | Não | Linha `Artigo: NOME` do bloco |
| `arquivo_origem` | texto | Sim | Nome do arquivo de origem (linhagem) |
| `sistema_origem` | texto | Sim | `ATUAL` (XLSX) ou `LEGADO` (`.rel`) |
| `confianca_data` | texto | Sim | `Registrada`, `Inferida`, `Inferida (suspeita)` ou `Ausente` |
| `confianca_identidade` | texto | Sim | `Observada` ou nível declarado de identidade derivada |

### Regras de negócio

- `id_venda = sistema_origem | numero_documento | data_emissao`
- `id_item_venda = id_venda | protocolo`
- A granularidade é o item: uma nota com N itens gera N linhas com o mesmo
  `id_venda`. A unicidade é validada em `id_item_venda`.
- Contagem de vendas = `COUNT(DISTINCT id_venda)`.
- Data oficial = data de emissão.
- Data ausente é preservada e sinalizada como aviso; a chave registra
  `SEM_DATA`.
- Maior cobertura substitui a menor quando o mesmo `id_item_venda` aparece em
  mais de um arquivo. Empate entre versões mais recentes vai integralmente para
  quarentena, sem ressuscitar versão antiga (D-014).
- Apenas registros elegíveis participam dessa precedência; uma versão inválida
  não remove uma versão válida anterior (D-022).
- Violações de linha são isoladas em quarentena; ausência de uma coluna
  obrigatória interrompe a publicação (D-019).
- Valores monetários são publicados em centavos inteiros; a view SQL converte
  para reais na borda de consulta (D-018).
- Zero monetário é aceito somente quando observado; ausência ou conversão
  inválida segue para quarentena, sem ser convertida em zero (D-021).
- Colisão de chave entre registros sem data é desambiguada com sufixo ordinal,
  nunca fundida (D-015).
- Identidade sem protocolo é derivada de venda, produto e ocorrência na fonte,
  sem depender do nome ou da linha física do arquivo (D-024).
- Data inferida é sempre declarada como tal em `confianca_data`.
- Duplicata exata (todas as colunas iguais, exceto `arquivo_origem`) é removida
  na consolidação.
- Segunda a sábado são dias operacionais; domingo não. Feriados não recebem
  tratamento especial.

## Contrato dos módulos

| Módulo | Entrada | Saída |
|--------|---------|-------|
| `ingestion` | Diretório com XLSX/XLS | DataFrame bruto com linhagem e procedência |
| `ingestion.legado` | Diretório com `.rel` | DataFrame do histórico legado + relatório do que foi ignorado |
| `transformation` | DataFrame bruto | DataFrame com código/descrição e chaves |
| `validation` | DataFrame padronizado | `ValidationReport` (erros e avisos) |
| `consolidation` | DataFrame bruto / padronizado | Sem duplicatas exatas; uma versão por item + relatório |
| `analytics` | DataFrame consolidado | Dict de KPIs |
| `export` | DataFrame consolidado | Parquet, CSV, JSON, Markdown |
| `query` | Parquet publicado + SQL | DataFrame com o resultado |
| `audit` | Etapas da execução | `PipelineRun` + `execucao.json` |
| `demo` | Semente | Arquivos sintéticos nos formatos de origem |

### Entradas e saídas do pipeline

- Entrada: `data/raw/` (XLSX/XLS) e `data/legado/` (`.rel`), este último opcional.
- Saída: `data/processed/vendas_consolidadas.parquet`,
  `data/processed/execucao.json` e histórico em
  `data/processed/auditoria/<id_execucao>.json`.
- Falha fatal: `data/processed/auditoria/<id_execucao>-falha.json`, sem alterar
  o marcador da última publicação válida.
- Saída opcional: `data/exports/vendas_consolidadas.csv`.
- Visão opcional: `data/processed/dashboard.html`, derivada do Parquet.
- Rejeitados: `data/quarantine/<id_execucao>/registros_rejeitados.parquet`.

## Casos de teste cobertos

1. Arquivo válido, arquivo parcial e múltiplos arquivos concatenados.
2. Colunas ausentes na origem.
3. Datas ausentes e datas inválidas.
4. Nota com múltiplos itens (unicidade correta).
5. Duplicatas exatas entre períodos.
6. Reprocessamento com resultado idêntico.
7. Layout de largura fixa do legado, incluindo cabeçalhos repetidos.
8. Reconstrução cronológica por CI, verificada por propriedade.
9. Datas corrompidas com sentinela e níveis de confiança.
10. Contrato de saída: colunas, ordem, tipos e ausência de redundância.
11. Consulta SQL sobre o Parquet publicado.
12. Fluxo completo de linha de comando.
13. União dos dois sistemas numa base contínua.
14. Recusa dos relatórios do legado que não são venda item a item.
15. Reconstrução de ano comparada a gabarito, e contenção de ano corrompido.

## Segurança e privacidade

- `data/` nunca é versionado.
- Nenhum nome de empresa, CNPJ ou identificador real aparece em arquivo
  versionado.
- O catálogo de produtos usado nos dados sintéticos é genérico.
- O pipeline funciona com qualquer ERP que produza relatórios na mesma
  estrutura.

## Backlog

**Concluído**

- [x] Leitura de XLSX/XLS hierárquico
- [x] Leitura dos três formatos `.rel` do legado
- [x] Reconstrução cronológica por CI
- [x] Padronização e chaves de negócio rastreáveis
- [x] Validação com separação entre erro e aviso
- [x] Consolidação e KPIs
- [x] Publicação em Parquet tipado
- [x] Consulta SQL local
- [x] Auditoria por execução
- [x] Dados sintéticos e testes de integração do legado
- [x] Interface de linha de comando
- [x] União do histórico legado com o atual em base única de série longa

**Futuro**

- [ ] Publicação do histórico de compras em base própria
- [ ] Análise de sazonalidade sobre o período completo
- [ ] Projeções e cenários
- [ ] Análise de campanhas
