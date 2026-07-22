# AGENTS.md — Diretrizes de desenvolvimento

Este documento define como trabalhar neste repositório — vale tanto para
pessoas quanto para agentes de IA usados no desenvolvimento.

## Stack

- Python 3.11+
- pandas e PyArrow para manipulação e publicação
- openpyxl e xlrd para leitura de XLSX/XLS
- DuckDB para consulta SQL local sobre o Parquet publicado
- pytest para testes, Ruff para lint e formatação

## Estrutura

```text
projetoAldebaran/
├── src/
│   ├── ingestion/       leitura de XLSX/XLS e dos .rel legados
│   │                    (rel_comum.py concentra o dialeto compartilhado)
│   ├── transformation/  padronização e chaves de negócio
│   ├── validation/      regras de negócio
│   ├── consolidation/   deduplicação entre períodos
│   ├── analytics/       KPIs
│   ├── export/          schema canônico, Parquet, CSV, JSON, Markdown
│   ├── query/           consulta SQL local
│   ├── audit/           rastreabilidade das execuções
│   ├── demo/            geração de dados sintéticos
│   ├── cli.py           interface de linha de comando
│   └── pipeline.py      orquestração
├── tests/               um arquivo por módulo
├── scripts/             utilitários
├── docs/                referência técnica dos formatos de origem
└── data/                NUNCA versionado
```

## Segurança de dados

- `data/` inteiro está no `.gitignore`. Nenhum dado de cliente sai da máquina.
- Nenhum nome de empresa, CNPJ ou identificador real em arquivo versionado.
- Exemplos em documentação e testes usam o catálogo sintético de `src/demo`.
- O código deve funcionar com quaisquer dados que sigam a mesma estrutura.

## Antes de mudar qualquer coisa

1. Leia `PROJECT_SPEC.md` (o que o pipeline faz) e `DECISIONS.md` (por que ele
   é assim).
2. Escreva os testes primeiro. Teste o contrato do módulo, não a existência da
   função.
3. Se a mudança altera uma regra de negócio ou um contrato de saída, registre
   a decisão em `DECISIONS.md` — com o contexto e a consequência, não só o que
   mudou.

## Regras de ouro

- **Os arquivos de origem são imutáveis.** Nada no pipeline escreve em
  `data/raw` ou `data/legado`.
- **Todo indicador é rastreável.** Se um número é publicado, tem de ser
  possível reconduzi-lo à execução que o produziu.
- **O que é inferido é declarado.** Datas reconstruídas carregam nível de
  confiança e preservam o valor original.
- **As regras de negócio ficam centralizadas.** Não espalhe validação pelos
  parsers.
- **Testes existentes não são alterados para passar.** Se um teste quebra, ou
  o código está errado, ou o contrato mudou de propósito — e nesse caso a
  mudança vai para `DECISIONS.md`.
- **Mínimo de código.** Sem abstração antes da terceira repetição.

## Verificação

```bash
pytest                              # suíte completa
ruff check src tests scripts        # lint
aldebaran demo && aldebaran run     # fluxo end-to-end
aldebaran query cobertura           # consulta sobre o publicado
```

O CI executa os quatro em Python 3.11 e 3.12 a cada push.

## Convenções

- Testes com pytest, um arquivo por módulo (`tests/test_ingestion.py`).
- Fixtures compartilhadas em `tests/conftest.py`.
- Docstrings nos módulos e funções públicas, explicando a decisão quando ela
  não for óbvia.
- Nomes de variáveis, funções e módulos em inglês; documentação, docstrings e
  mensagens ao usuário em português brasileiro.
- Commits com prefixo convencional em inglês (`feat:`, `fix:`, `docs:`,
  `test:`, `refactor:`, `chore:`) e corpo descritivo em PT-BR.

## Uso de agentes de IA

Agentes são usados para implementação de escopo fechado. O critério é o mesmo
aplicado a qualquer contribuição:

- o escopo do passo é definido antes, e o que sai fora dele é revertido;
- a suíte de testes roda a cada passo;
- decisões de arquitetura e de regra de negócio são revisadas por pessoa, não
  delegadas.
