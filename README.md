# Aldebaran 🔭

> Pipeline ETL inteligente para transformar relatorios ERP hierarquicos em dados analiticos limpos, KPIs auditaveis e saidas prontas para BI.

[![Python 3.11+](https://img.shields.io/badge/python-3.11_%7C_3.12-blue?logo=python)](https://www.python.org/)
[![CI](https://github.com/edevandor/projetoAldebaran/actions/workflows/ci.yml/badge.svg)](https://github.com/edevandor/projetoAldebaran/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Testes](https://img.shields.io/badge/testes-81_verdes-brightgreen)](https://github.com/edevandor/projetoAldebaran/actions)

---

## Motivacao

Relatorios ERP geram dados preciosos, mas presos em formatos que ferramentas tradicionais nao entendem.

Planilhas de vendas saem do sistema com uma estrutura hierarquica de 3 niveis:

```
Responsavel: Carlos Silva
  └── Artigo: Venda Direta
       ├── Produto A  ...  R$ 1.200,00
       ├── Produto B  ...  R$ 3.500,00
       └── Total: Venda Direta  R$ 4.700,00
```

`pd.read_excel()` falha. Pipelines de dados tradicionais falham. O dado valioso fica preso no formato do relatorio.

**Aldebaran resolve isso** — um parser inteligente com maquina de estados que entende a hierarquia, extrai o contexto (vendedor, categoria) e produz dados relacionais limpos para qualquer ferramenta de BI consumir.

---

## Arquitetura

```
data/raw/  →  Ingestao  →  Padronizacao  →  Validacao  →  Consolidacao  →  Analytics  →  Exportacao
                   │              │               │              │              │              │
              parser.py     standardizer    validator     consolidator    kpis.py      formatters.py
              directory.py                                                                 auditor.py
```

### Modulos

| Modulo | Responsabilidade |
|--------|-----------------|
| **ingestion** | Leitura de XLSX/XLS, parsing do formato ERP hierarquico com maquina de estados (5 estados: METADATA → ARTICLE_HEADER → COLUMN_HEADER → DATA → TOTAL) |
| **transformation** | Separacao codigo/descricao dos produtos, geracao de IDs de venda |
| **validation** | Regras de negocio: campos obrigatorios, unicidade de IDs, integridade dos dados |
| **consolidation** | Remocao de duplicatas exatas entre periodos |
| **analytics** | Calculo de KPIs: faturamento, ticket medio, top produtos, vendas por mes |
| **audit** | Rastreabilidade de execucao: PipelineRun com timestamp, etapas, erros |
| **export** | Saída para CSV (Looker Studio / Power BI), JSON, Markdown |

---

## Inicio Rapido

```bash
# 1. Clone e prepare o ambiente
git clone https://github.com/edevandor/projetoAldebaran.git
cd projetoAldebaran
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Gere dados sinteticos para teste
python scripts/gerar_dados_sinteticos.py

# 3. Execute o pipeline
python -c "
from src.pipeline import run_pipeline
resultado = run_pipeline()
kpis = resultado['kpis']
print(f'Faturamento total: R$ {kpis[\"total_faturamento\"]:_.2f}')
print(f'Itens vendidos: {kpis[\"total_itens\"]}')
print(f'Ticket medio: R$ {kpis[\"ticket_medio\"]:_.2f}')
"

# 4. Execute os testes
pytest
```

---

## Modelo de Dados

| Campo | Tipo | Origem |
|-------|------|--------|
| `produto` | texto | Coluna A do XLSX |
| `data_emissao` | data | Coluna H |
| `tipo_documento` | texto | Prefixo da NF |
| `numero_documento` | texto | Coluna J (NF) |
| `id_venda` | texto | `tipo_documento + NF + data` |
| `protocolo` | texto | Coluna I |
| `id_item_venda` | texto | `id_venda + protocolo` |
| `valor_total_venda` | decimal | Coluna N |
| `quantidade` | decimal | Coluna G |
| `unidade_medida` | texto | Coluna F |
| `responsavel` | texto | Hierarquia do XLSX (vendedor) |
| `artigo` | texto | Hierarquia do XLSX (categoria) |

### Regras de Negocio

- `id_venda = tipo_documento + numero_documento + data_emissao`
- `id_item_venda = id_venda + protocolo`
- Datas ausentes preservadas (migracao de servidor em 2023 gerou falhas de datacao — o parser nao descarta linhas, a validacao decide)
- Toda venda indexada por `responsavel` e `artigo` herdados da hierarquia

---

## KPIs Gerados

O pipeline calcula automaticamente (exemplo com dados sinteticos):

| Metrica | Exemplo |
|---------|--------|
| Faturamento total | R$ 9,5 milhoes |
| Notas fiscais | 143 |
| Itens vendidos | 144 |
| Ticket medio | R$ 66.434 |
| Top 10 produtos (valor e quantidade) | Ranking completo |
| Vendas por mes | Serie temporal mensal

Saídas disponiveis em CSV (Looker Studio / Power BI), JSON e Markdown.

---

## Testes

```
81 passed, 0 failed, 0 skipped
```

Cada modulo tem testes dedicados validando contratos, nao existencia. Os testes de integracao executam o pipeline completo com dados sinteticos.

---

## Estrutura do Projeto

```
projetoAldebaran/
├── src/
│   ├── ingestion/         # Parsers XLSX e .rel
│   ├── transformation/    # Padronizacao e geracao de IDs
│   ├── validation/        # Regras de negocio
│   ├── consolidation/     # Deduplicacao
│   ├── analytics/         # Calculo de KPIs
│   ├── audit/             # Rastreabilidade
│   └── export/            # Formatos de saida
├── tests/                 # Testes pytest
├── scripts/               # Utilitarios (gerador sintetico, etc.)
├── docs/                  # Documentacao detalhada
├── data/                  # Dados brutos (NUNCA versionados)
├── .github/workflows/     # CI/CD
├── pyproject.toml
└── requirements.txt
```

---

## Licenca

MIT — livre para uso, estudo e modificacao.

---

> **Aldebaran** e o nome da estrela mais brilhante da constelacao de Touro (α Tauri).  
> O projeto e um template generico de ETL — funciona com qualquer ERP que produza relatorios no mesmo formato estrutural.
