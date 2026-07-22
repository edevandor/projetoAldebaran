# PROJECT_SPEC.md — Especificação do Projeto

## Visão Geral

Pipeline ETL para processamento de mapas estatísticos de vendas (XLSX).
Consolida históricos, valida dados contra regras de negócio e calcula KPIs
auditáveis para análise posterior por IA.

## Objetivo

Preparar dados de vendas para análise por IA, consolidando históricos,
validando dados e calculando KPIs reproduzíveis.

### Princípios

- A IA interpreta; o pipeline calcula.
- Arquivos originais nunca são alterados.
- Todo indicador deve ser auditável.
- Toda regra de negócio deve ser centralizada.
- A base consolidada é a fonte oficial para análises.

## Escopo

- Processar arquivos de 2023 em diante.
- Suportar XLS, XLSX e CSV.
- Futuramente incorporar histórico 2002–2022 via módulo específico.

## Arquitetura

### Fluxo

```
data/raw/ → Ingestão → Padronização → Validação → Consolidação
→ KPIs → Exportação → IA
```

### Módulos

| Módulo | Função |
|--------|--------|
| **Ingestão** | Leitura de XLSX/XLS/CSV, parsing do formato ERP hierárquico |
| **Padronização** | Normalização de colunas, tipos, datas, remoção de metadados |
| **Validação** | Regras de negócio e integridade dos dados |
| **Consolidação** | União de períodos, deteção de sobreposições |
| **Motor Analítico** | Cálculo de KPIs e indicadores |
| **Auditoria** | Rastreabilidade e reprodutibilidade dos resultados |
| **Exportação** | Saída JSON, Markdown |
| **Camada IA** | Consumo dos dados consolidados por LLM |

## Fonte de Dados

### Origem

Sistema ERP gera reports "Mapa Estatístico de Vendas" no formato XLSX.

### Estrutura do Raw

Os XLSX têm formato hierárquico típico de ERP:

1. **Metadados** (linhas 1-4): empresa, data de extração, página, responsável
2. **Blocos por artigo** (repetem-se):
   - `"Artigo: NOME"` — cabeçalho do artigo
   - Linha de cabeçalho de colunas
   - Linhas de venda (dados)
   - `"Total: Artigo: NOME"` — subtotal
3. **17 colunas** originais; 10 campos mapeados no modelo de dados

## Modelo de Dados

| Campo | Tipo | Obrigatório | Origem |
|-------|------|-------------|--------|
| `produto` | texto | Sim | Coluna 1 do raw |
| `data_emissao` | data | Sim | Coluna 8 do raw |
| `tipo_documento` | texto | Sim | Derivado (NF, etc.) |
| `numero_documento` | texto | Sim | Coluna 10 (NF Nº) |
| `id_venda` | texto | Sim | `tipo_documento + numero_documento + data_emissao` |
| `protocolo` | texto | Condicional | Coluna 9 |
| `id_item_venda` | texto | Condicional | `id_venda + protocolo` |
| `valor_total_venda` | decimal | Sim | Coluna 14 |
| `quantidade` | decimal | Não | Coluna 7 |
| `unidade_medida` | texto | Não | Coluna 6 |

### Regras de Negócio

- `id_venda = tipo_documento + numero_documento + data_emissao`
- Contagem de vendas = COUNT DISTINCT(id_venda)
- `id_item_venda = id_venda + protocolo`
- Data oficial = Data Emissão
- Segunda a sábado operacionais. Domingo não operacional.
- Feriados não recebem tratamento especial.
- Versão consolidada substitui parcial. Nunca duplicar períodos.

## Casos de Teste

1. Arquivo válido
2. Arquivo duplicado
3. Arquivo parcial
4. Colunas ausentes
5. Datas inválidas
6. Valores divergentes
7. Sobreposição de períodos
8. Reprocessamento
9. KPIs reproduzíveis

## Pipeline — Contrato dos Módulos

### Entrada do Pipeline
- Diretório: `data/raw/`
- Formato: XLSX (14 ficheiros, Q1-Q4 2023-2025, Q1-Q2 2026)
- Tamanho total: ~15MB

### Saída do Pipeline
- `data/staging/` — dados padronizados (CSV/Parquet)
- `data/processed/` — dados consolidados e validados
- `data/exports/` — relatórios finais (JSON, Markdown)

### Subprodutos
- `logs/` — registo de execução
- `config/` — parametrização (mapeamento de colunas, aliases)

## Segurança e Privacidade

- `data/` nunca é versionado
- Nenhum identificador real do cliente nos ficheiros de código/docs
- O pipeline é um **template genérico** — funciona com qualquer ERP que produza XLSX no mesmo formato estrutural
- Pronto para portfólio / código aberto

## Backlog

### MVP
- [✅] Leitura XLSX/XLS/CSV
- [✅] Padronização de colunas
- [✅] Consolidação
- [✅] KPIs básicos
- [✅] Exportação JSON e Markdown

### Futuro
- [ ] TXT 2002-2022
- [✅] Sazonalidade
- [ ] Projeções
- [ ] Campanhas
- [ ] Interface gráfica
