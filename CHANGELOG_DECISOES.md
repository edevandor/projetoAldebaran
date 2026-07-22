# CHANGELOG_DECISOES.md — Registo de Decisões Arquiteturais

Decisões técnicas do projeto, com essência e consequência.

---

## D-001 — Estrutura `src/` plana

Módulos como pacotes independentes (`from ingestion import parse_xlsx`)
em vez de namespace aninhado `projeto_aldebaran.ingestion`. O projeto
não é publicado no PyPI, a simplicidade de import vale mais.

---

## D-002 — `data/` inteiro no `.gitignore`

Nenhum dado de cliente sai da máquina. O pipeline executa localmente;
CI/CD precisaria de dados sintéticos.

---

## D-003 — Codinome Aldebaran

Nome da estrela α Tauri. Sem relação com cliente ou segmento. Seguro
para portfólio.

---

## D-004 — Parser dedicado com openpyxl

Formato ERP hierárquico inviabiliza `pd.read_excel()` directo. Máquina
de estados linha a linha com openpyxl (modo read_only por performance).
Reutilizável para qualquer ERP de formato semelhante.

---

## D-005 — PT-BR na doc, commits mistos

Documentação em português. Commits com prefixo convencional em inglês
(chore:, feat:, fix:) e corpo descritivo em PT-BR. Código-fonte em inglês.

---

## D-006 — Indexação hierárquica: responsável + artigo

**Data:** 2026-07-13

### Contexto

As vendas nos XLSX estão organizadas em 3 níveis hierárquicos:
Responsável → Artigo → linhas de venda.
O parser original extraía apenas as linhas, perdendo o contexto
de vendedor e categoria de produto.

### Decisão

O parser (`parser.py`) passou a rastrear `current_responsavel` e
`current_artigo` durante a máquina de estados, injectando ambos em
cada linha extraída. A detecção é case-insensitive e tolera acentos
para suportar variações entre ficheiros.

### Consequência

Cada venda tem agora `responsavel` + `artigo` indexados.
Algumas vendas têm "null" como responsável (ERP sem vendedor atribuído).
O pipeline passou de 63 para 66 testes.
