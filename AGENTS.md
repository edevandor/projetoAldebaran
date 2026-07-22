# AGENTS.md — Diretrizes para Agentes IA

Este documento define como os agentes IA (Hermes, Codex, subagentes)
devem operar no projetoAldebaran.

## Stack

- **Python 3.12+**, com openpyxl + pandas
- Estrutura `src/` plana (módulos como pacotes independentes)
- Testes com `pytest`
- Ambiente virtual em `.venv/`

## Estrutura do Projeto

```
ProjetoAldebaran/
├── docs/                  ← Documentação numerada (01_ a 06_)
├── data/                  ← NUNCA versionado (gitignore)
├── config/                ← Configurações genéricas
├── src/                   ← Código-fonte
│   ├── ingestion/         ← Leitura de XLSX/XLS/CSV
│   ├── validation/        ← Regras de negócio e integridade
│   ├── transformation/    ← Padronização de colunas e tipos
│   ├── analytics/         ← Cálculo de KPIs e indicadores
│   ├── audit/             ← Rastreabilidade e reprodutibilidade
│   └── export/            ← Saída JSON, Markdown, etc.
├── tests/                 ← Testes paralelos ao src/
├── scripts/               ← Utilitários avulsos
├── pyproject.toml
└── requirements.txt
```

## Segurança de Dados

- `data/` inteiro está no `.gitignore` — **nenhum dado** sai da máquina
- Nenhum nome de empresa, CNPJ, ou identificador real aparece em ficheiros versionados
- O código deve funcionar com **quaisquer dados** que sigam o mesmo formato estrutural

## Fluxo de Trabalho por Microciclo (MC)

### Antes de Começar

1. Ler: `AGENTS.md`, `PROJECT_SPEC.md`, `PLANS.md`, `CHANGELOG_DECISOES.md`
2. Escrever **testes primeiro** (TDD) — mínimo 2 testes por MC
3. Dividir o MC em passos `X.Y.Z` no `PLANS.md`

### Cada Passo (X.Y.Z)

1. **Prompt atómico para Codex** — auto-contido, embute só as 1-3 regras relevantes
   - Incluir: `"NÃO adicionar nada além do listado neste prompt"`
   - Codex **não lê** AGENTS.md / PLANS.md / PROJECT_SPEC — Hermes embute o necessário
2. **Codex executa** via `terminal(pty=true)`
3. **Verificar** `git diff --stat` — se Codex modificou fora do escopo, reverter com `git checkout`
4. **Executar `pytest`** — bateria completa
   - Falha por dependência futura → ignora
   - Falha no contrato → diagnostica, cria teste de regressão, corrige (máx 3 tentativas Codex)
5. Avançar

### Após o MC

1. **Bateria final:** `pytest`
2. **Propor commit** com lista de passos
3. Aguardar autorização do usuário
4. Commitar com prefixo convencional (chore:, feat:, fix:, docs:, test:) e descrição em PT-BR
5. Atualizar `PLANS.md` e `CHANGELOG_DECISOES.md` se aplicável

### Regras de Ouro

- **TEC-005:** Testes existentes nunca alterados sem justificativa + aprovação
- **TEC-006:** Mínimo de código possível — sem abstrações prematuras
- **Originais nunca alterados** — os XLSX brutos são imutáveis
- **Auditabilidade** — todo indicador deve ser reproduzível
- **Regras de negócio centralizadas** — não espalhar regras pelos módulos

## Pair Programming: Hermes + Codex

| Papel | Quem | Responsabilidade |
|-------|------|-----------------|
| **Arquiteto** | Hermes (DeepSeek) | Decisões técnicas, revisão, testes, commit |
| **Executor** | Codex CLI | Implementação de passos atómicos com escopo fechado |

Codex é usado para **lógica complexa** (parser, transformação, validação cruzada).
Para extracções simples (renomear, mover funções), usar `patch` directo.

## Convenções de Código

- Testes com `pytest` — um ficheiro por módulo: `tests/test_ingestion.py`, etc.
- Fixtures em `tests/conftest.py`
- Docstrings nos módulos públicos
- Nomes de variáveis e funções em inglês
- Commits com prefixo padrão e corpo em PT-BR
