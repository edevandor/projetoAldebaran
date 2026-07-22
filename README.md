# Aldebaran

Pipeline que transforma relatórios de um ERP legado em uma base comercial consultável, cobrindo aproximadamente 25 anos de histórico de vendas — sem acesso ao banco de dados de origem.

[![Python 3.11+](https://img.shields.io/badge/python-3.11_%7C_3.12-blue?logo=python)](https://www.python.org/)
[![CI](https://github.com/edevandor/projetoAldebaran/actions/workflows/ci.yml/badge.svg)](https://github.com/edevandor/projetoAldebaran/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licença-MIT-green)](LICENSE)
[![Testes](https://img.shields.io/badge/testes-222-brightgreen)](https://github.com/edevandor/projetoAldebaran/actions)

> O caso de negócio e os volumes descritos abaixo pertencem à execução original, sobre dados reais de um ERP. Este repositório é uma **implementação pública, sanitizada e reduzida** do processo técnico utilizado: dados sintéticos, escala menor, catálogo genérico, sem qualquer conexão com o ERP. Os números do caso real são relato operacional, não uma saída reproduzível deste código sobre o dataset público.

Para uma visão curta orientada a gestores e recrutamento, consulte a
[`leitura executiva`](docs/leitura-executiva.md).

## O caso de negócio

O histórico comercial da operação existia, mas não era consultável.

Estava dividido em dois sistemas e em dois formatos, nenhum deles legível por ferramenta de análise:

**O ERP atual** exportava o *Mapa Estatístico de Vendas* em XLSX — só que não era uma tabela. Era um relatório de impressão convertido para planilha: blocos hierárquicos de três níveis (responsável → artigo → linhas de venda), com cabeçalhos repetidos e subtotais intercalados entre os dados. `pd.read_excel()` retorna ruído sobre esse arquivo.

**O ERP anterior**, que cobria de 2002 a 2022, exportava arquivos `.rel`: texto de largura fixa em 132 colunas, codificação latin-1, números no formato brasileiro, cabeçalho de página a cada bloco. Mais de **1 milhão de linhas**, representando centenas de milhares de vendas. Ninguém trabalhava com esse arquivo. Vinte anos de histórico comercial que, na prática, não existiam para a operação.

Não havia acesso direto ao banco. Não havia réplica de leitura. O que existia era exportação de relatório.

### O custo semanal

Como o histórico longo era inacessível, a operação trabalhava apenas com a janela curta.

Toda semana, a pessoa responsável pela TI extraía do ERP o XLS da semana de vendas, selecionava manualmente o que entraria na análise e montava o recorte para quem pedia. Toda semana, de novo. Isso significava:

- horas recorrentes da TI gastas em trabalho manual repetitivo, fora da responsabilidade principal — manter os sistemas da operação funcionando;
- risco de erro humano a cada recorte, sem rastro de como o número foi produzido;
- análise limitada à última semana, porque consolidar meses ou anos manualmente era inviável;
- nenhuma leitura de sazonalidade, justamente em uma operação em que ela é determinante.

## O que foi construído

Um pipeline local que lê os formatos como eles são e publica uma base consultável:

1. leitura do XLSX hierárquico por máquina de estados, que reconhece os cinco tipos de linha do relatório (metadados, cabeçalho de artigo, cabeçalho de colunas, dados e totais) e descarta o que não é venda;
2. herança do contexto hierárquico — cada item de venda recebe o responsável e o artigo do bloco em que estava, informação que o formato original só expressava pela posição da linha;
3. leitura dos `.rel` legados por posição de coluna, com conversão de números e datas do padrão brasileiro;
4. reconstrução cronológica do legado a partir do Controle Interno (CI), quando a data impressa é inconfiável;
5. padronização: separação de código e descrição do produto, e geração de chaves de negócio rastreáveis;
6. validação contra as regras de negócio, distinguindo o que invalida um registro do que apenas o sinaliza;
7. consolidação e remoção de duplicatas exatas entre períodos;
8. publicação em Parquet tipado, consultável em SQL local, com exportação opcional em CSV padronizado;
9. auditoria de cada execução, registrando etapas, contagens e resultado da validação.

## O resultado

O histórico deixou de ser um conjunto de relatórios e passou a ser uma base.

- **Aproximadamente 25 anos de histórico comercial** (2002 em diante) tornaram-se consultáveis em um único lugar, incluindo as duas décadas do sistema anterior que nenhuma ferramenta lia. O pipeline une os dois sistemas na mesma base, e cada linha declara de qual deles veio.
- O recorte semanal manual da TI deixou de ser o caminho para obter dados de venda: a consolidação passou a ser um comando reproduzível, e não uma tarefa de pessoa.
- Perguntas que antes não tinham como ser respondidas — sazonalidade por mês ao longo dos anos, comportamento por produto, concentração por responsável — passaram a ser uma consulta SQL sobre o Parquet publicado.
- Cada número publicado é rastreável até a execução que o produziu, e cada chave de venda pode ser decomposta de volta em documento, data e protocolo.

O pipeline organiza e publica. Ele não escreve no ERP, não altera os arquivos de origem e não substitui a interpretação de quem conhece a operação.

## O problema técnico central

### Um relatório não é uma tabela

O XLSX do ERP tem esta forma:

```text
Responsável: Responsável A
  Artigo: Venda Direta
    Produto             Und   Qtde   Data Emissão   NF Nº        Total Venda
    000101 - PRODUTO A   UN    2,00   15/01/2025    001-100001      1.500,50
    000204 - ITEM B      PC    4,00   15/01/2025    001-100001        500,00
    Total: Venda Direta                                             2.000,50
  Artigo: Reposição
    ...
Total: Responsável: Responsável A
```

O vendedor e a categoria não são colunas: são linhas acima dos dados. O subtotal tem a mesma aparência de uma venda. A leitura direta produz uma tabela em que contexto, dados e totais estão misturados — e em que somar a coluna de valor conta cada venda duas vezes.

O parser resolve isso como máquina de estados: percorre linha a linha, mantém em memória o responsável e o artigo vigentes, reconhece transições de bloco e emite apenas linhas de venda, já com o contexto herdado.

### Duas décadas com o ano ambíguo

Nos `.rel` analíticos de vendas do sistema legado, o ano aparece com dois dígitos. Ao longo de duas décadas, `02` e `22` não podem ser interpretados isoladamente sem conhecer o período e a sequência do relatório.

O que permanece íntegro é o **CI (Controle Interno)** — um sequencial que só cresce ao longo do tempo. O parser usa essa monotonicidade como eixo cronológico e valida cada ano candidato contra o período declarado no cabeçalho. Um ano fora desse intervalo é contido no próprio registro e marcado como suspeito, em vez de empurrar toda a série para o futuro.

Cada data reconstruída chega à base como `Inferida` ou `Inferida (suspeita)`. A inferência nunca é apresentada como se fosse leitura direta da origem.

## Arquitetura

```text
XLSX hierárquico (ERP atual)        .rel largura fixa (ERP legado, 2002–2022)
        │                                        │
        ▼                                        ▼
   ┌─────────────────────────────────────────────────────┐
   │ Ingestão      máquina de estados · posição de coluna │
   │               reconstrução cronológica por CI        │
   ├─────────────────────────────────────────────────────┤
   │ Consolidação  duplicatas exatas · versão do período  │
   ├─────────────────────────────────────────────────────┤
   │ Padronização  código/descrição · chaves de negócio   │
   ├─────────────────────────────────────────────────────┤
   │ Validação     campos obrigatórios · unicidade        │
   │               avisos para lacunas conhecidas         │
   ├─────────────────────────────────────────────────────┤
   │ Publicação    Parquet tipado · CSV opcional          │
   │               auditoria da execução                  │
   └─────────────────────────────────────────────────────┘
                          │
                          ▼
              SQL local (DuckDB) · BI
```

### Módulos

| Módulo | Responsabilidade |
|--------|-----------------|
| `ingestion` | Leitura de XLSX/XLS e dos três formatos `.rel`, com reconhecimento do tipo de relatório |
| `transformation` | Separação de código e descrição, geração das chaves de negócio |
| `validation` | Regras de negócio, separando erros de avisos |
| `consolidation` | Duplicatas exatas e resolução de versão quando um período é reexportado |
| `analytics` | KPIs: faturamento, ticket médio, ranking de produtos, série mensal |
| `export` | Schema canônico de saída, Parquet, CSV, JSON e Markdown |
| `query` | Consulta SQL local sobre o Parquet publicado |
| `audit` | Registro rastreável de cada execução |
| `demo` | Geração de dados sintéticos nos formatos de origem |

## Contrato de saída

Uma única definição de schema (`src/export/schema.py`) governa as duas camadas de saída, de modo que Parquet e CSV descrevem exatamente o mesmo contrato:

| Coluna | Tipo | Observação |
|--------|------|-----------|
| `id_execucao` | texto | Liga a linha ao registro da execução |
| `id_item_venda` | texto | Chave primária — a granularidade é o item |
| `id_venda` | texto | Chave da venda (uma venda, N itens) |
| `data_emissao` | data | Tipo temporal nativo, não texto |
| `tipo_documento` | texto | Série do documento |
| `numero_documento` | texto | Número da nota |
| `protocolo` | texto | Identificador do item; pode faltar na origem |
| `codigo_produto` | texto | |
| `descricao_produto` | texto | |
| `quantidade` | decimal | |
| `unidade_medida` | texto | |
| `valor_total_venda_centavos` | inteiro | Valor monetário canônico e exato |
| `responsavel` | texto | Herdado da hierarquia do relatório |
| `artigo` | texto | Herdado da hierarquia do relatório |
| `arquivo_origem` | texto | Linhagem: de qual arquivo veio a linha |
| `sistema_origem` | texto | `ATUAL` ou `LEGADO` |
| `confianca_data` | texto | Como a data foi obtida: `Registrada`, `Inferida`, `Inferida (suspeita)` ou `Ausente` |
| `confianca_identidade` | texto | Declara quando a identidade precisou ser derivada por falta de protocolo ou data |

### Regras de negócio

- `id_venda = sistema_origem | numero_documento | data_emissao`
- `id_item_venda = id_venda | protocolo`
- **A granularidade do dataset é o item, não a venda.** Uma nota com quatro produtos produz quatro linhas com o mesmo `id_venda`. Por isso a unicidade é validada em `id_item_venda`; exigi-la em `id_venda` acusaria como erro o comportamento normal da operação.
- Contagem de vendas = `COUNT(DISTINCT id_venda)`.
- Datas ausentes são preservadas e sinalizadas, nunca descartadas: a migração de servidor de 2023 deixou vendas sem datação, e descartá-las apagaria faturamento real. A chave registra `SEM_DATA` de forma explícita.
- **Um período reexportado não é contado duas vezes.** Quando o mesmo item aparece em relatórios de coberturas diferentes, prevalece a maior cobertura. Empates entre versões mais recentes vão para quarentena; uma versão antiga nunca reaparece como se fosse atual.
- **Sem data, duas vendas não viram uma.** Documentos de mesmo número e protocolo que perderam a data receberiam a mesma chave; a colisão é desambiguada e sinalizada, em vez de fundir dois registros.
- **O que é inferido é declarado.** As datas do legado são reconstruídas a partir do CI e chegam à base marcadas como `Inferida`, nunca como se fossem leitura direta.
- **Dinheiro é exato na camada publicada.** O Parquet guarda centavos inteiros; a view SQL expõe reais para consulta.
- **Toda execução é identificável.** Parquet e auditoria compartilham `id_execucao`; entradas e saídas têm SHA-256 registrado.
- Os arquivos de origem nunca são alterados.

## Como executar

```bash
git clone https://github.com/edevandor/projetoAldebaran.git
cd projetoAldebaran

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Gerar os dados sintéticos, nos mesmos formatos da origem (XLSX hierárquico e os três `.rel` legados):

```bash
aldebaran demo
```

Executar o pipeline e publicar o Parquet:

```bash
aldebaran run
```

```text
[2026-09-16T13:25:33+00:00] ✓ 8 etapas, 533 linhas, 0.1s

  ingestao          0.03s  linhas=277
  ingestao_legado   0.01s  linhas=256, arquivos=1, ignorados=2
  deduplicacao      0.00s  linhas=533, removidas=0
  padronizacao      0.01s  linhas=533, colisoes_chave=0
  versoes           0.00s  linhas=533, substituidas=0
  validacao         0.00s  linhas=533, erros=0, avisos=0, rejeitadas=0
  analytics         0.01s
  parquet           0.02s  linhas=533, tamanho_mb=0.03

  Faturamento    R$ 1.443.435,08
  Notas fiscais  249
  Itens          533
  Ticket médio   R$ 5.796,93

  legado: vendas_analitico.rel — 256 linhas
  legado: compras_analitico.rel — ignorado (movimento de compra, não de venda)
  legado: vendas_sintetico.rel — ignorado (relatório agregado, sem granularidade de venda)

  Validação: OK - 533 linhas, 0 erros
```

O histórico sai unificado, e a cobertura pode ser conferida em um comando:

```bash
aldebaran query cobertura
```

```text
sistema_origem primeira_venda ultima_venda  itens  notas  itens_sem_data
         ATUAL     2025-01-04   2026-06-24    277    144             0.0
        LEGADO     2002-01-22   2022-12-23    256    105             0.0
         TOTAL     2002-01-22   2026-06-24    533    249             0.0
```

Consultar a base publicada em SQL, sem servidor e sem carga intermediária:

```bash
aldebaran query "SELECT responsavel, COUNT(DISTINCT id_venda) AS notas
                 FROM vendas GROUP BY 1 ORDER BY 2 DESC"
```

Consultas prontas acompanham o projeto (`aldebaran query --listar`):

| Consulta | Pergunta que responde |
|----------|----------------------|
| `sazonalidade` | Como o faturamento se distribui mês a mês |
| `top-produtos` | Quais produtos concentram faturamento e volume |
| `responsaveis` | Notas, faturamento e ticket médio por responsável |
| `itens-por-nota` | Quantos itens compõem cada venda |
| `cobertura` | Período coberto por sistema, volume e registros sem data |
| `procedencia` | Quanto do histórico tem data lida e quanto tem data inferida |

Gerar uma visão executiva HTML, local e filtrável por sistema:

```bash
aldebaran dashboard
```

Ela consome somente o Parquet publicado e não adiciona regras ao pipeline.

Para ferramentas de BI que não leem Parquet, o CSV padronizado é opcional:

```bash
aldebaran run --csv
```

Cada execução grava `data/processed/execucao.json` e preserva uma cópia em
`data/processed/auditoria/<id_execucao>.json`. O registro contém versão do
pipeline e do schema, contagens por etapa e SHA-256 das entradas e saídas.
Linhas que violam o contrato não contaminam a base: ficam em
`data/quarantine/<id_execucao>/registros_rejeitados.parquet`, e a execução
termina com status parcial. Falhas fatais também deixam auditoria histórica,
sem substituir o marcador da última publicação válida. A publicação é
preparada em staging, de modo que
uma falha tratável na geração ou promoção restaura o conjunto anterior. Como
qualquer publicação baseada em arquivos, isso não equivale a uma transação de
filesystem diante de encerramento abrupto da máquina.

## Testes

```text
222 passed
```

A suíte cobre o contrato de cada módulo, e não a sua existência. Inclui:

- os três parsers do legado, exercitados sobre arquivos `.rel` sintéticos que reproduzem o layout de 132 colunas, a codificação latin-1 e as datas corrompidas da origem;
- a reconstrução cronológica, comparada com o gabarito de anos que o gerador produz — verificar apenas que o ano nunca decresce não provaria nada, já que o algoritmo garante isso por construção e passaria mesmo sobre uma série inteiramente errada;
- a contenção de um ano corrompido, que antes arrastava a série inteira;
- a união dos dois sistemas na mesma base, incluindo a recusa dos relatórios que não são venda item a item;
- as regras que decidem identidade e versão: período reexportado, registro sem data e linha idêntica em dois arquivos;
- as regras de negócio, incluindo o caso de uma nota com vários itens;
- o contrato de saída, incluindo a tipagem temporal que permite filtrar por data em SQL sem `CAST`;
- o fluxo completo de linha de comando, da geração dos dados à consulta.

O CI executa lint, a suíte completa em Python 3.11 e 3.12, e um teste end-to-end que gera os dados, executa o pipeline e consulta o resultado.

Para medir o núcleo tabular com um volume explícito, sem confundi-lo com o
tempo de parsing dos formatos de origem:

```bash
python scripts/benchmark_pipeline.py --rows 100000
```

## Governança e decisões técnicas

As decisões que explicam por que o pipeline é como é estão em [`DECISIONS.md`](DECISIONS.md), inclusive as que foram revistas e o motivo. A especificação funcional está em [`PROJECT_SPEC.md`](PROJECT_SPEC.md) e as diretrizes de desenvolvimento em [`AGENTS.md`](AGENTS.md).

A referência técnica dos formatos de origem — o layout de colunas do `.rel`, os tipos de linha do XLSX hierárquico e o método de reconstrução das datas — está em [`docs/formatos-de-origem.md`](docs/formatos-de-origem.md). Padrões de consulta sobre a base publicada estão em [`docs/consultas.md`](docs/consultas.md).

## Limites conhecidos

- O pipeline trabalha sobre exportações de relatório, não sobre conexão direta ao banco do ERP.
- As datas reconstruídas do legado são inferência, não dado de origem; o nível de confiança acompanha cada registro e a data impressa original é preservada.
- Dos três relatórios do legado, apenas o analítico de vendas alimenta o histórico. O sintético é agregado por item, sem granularidade de venda, e o de compras é movimento de entrada — somá-los ao faturamento inventaria receita. O pipeline os reconhece e declara o motivo de cada um ficar de fora.
- O parser de compras também implementa uma reconstrução experimental baseada em distribuição de CIs no período, mas compras não alimentam a base de faturamento. Essa inferência permanece documentada e testada para uma futura base própria.
- A escrita de volta no ERP está fora do escopo.
- Os dados públicos deste repositório são sintéticos: servem para verificar o comportamento do pipeline, não para reproduzir os números do caso real.

## Licença

MIT.

---

> **Aldebaran** é a estrela mais brilhante da constelação de Touro (α Tauri).
