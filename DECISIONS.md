# DECISIONS.md — Decisões técnicas

Por que o pipeline é como é. Cada decisão registra o contexto que a motivou
e a consequência que trouxe — inclusive as que foram revistas depois.

---

## D-001 — Estrutura `src/` plana

Os módulos são pacotes independentes (`from ingestion import parse_xlsx`), em
vez de um namespace aninhado (`projeto_aldebaran.ingestion`).

O projeto não é publicado no PyPI. A simplicidade do import vale mais do que a
proteção de namespace que ninguém vai exercer.

---

## D-002 — `data/` inteiro no `.gitignore`

Nenhum dado de cliente sai da máquina. O pipeline executa localmente.

**Consequência:** a verificação pública depende de dados sintéticos — o que
levou ao módulo `demo` (D-010).

---

## D-003 — Codinome Aldebaran

Nome da estrela α Tauri. Sem relação com cliente, segmento ou produto. Seguro
para portfólio.

---

## D-004 — Parser dedicado, com máquina de estados

O formato hierárquico do relatório inviabiliza `pd.read_excel()`: contexto,
dados e subtotais ocupam linhas do mesmo tipo.

A leitura é feita linha a linha com openpyxl em modo `read_only`, sobre uma
máquina de estados de cinco estados. É reutilizável por qualquer ERP que
produza relatórios com a mesma estrutura.

---

## D-005 — Documentação em PT-BR, código em inglês

Documentação e mensagens em português brasileiro. Nomes de variáveis, funções
e módulos em inglês. Commits com prefixo convencional em inglês e corpo em
PT-BR.

---

## D-006 — Indexação hierárquica: responsável e artigo

**Contexto.** As vendas estão organizadas em três níveis — responsável →
artigo → linhas. O parser original extraía apenas as linhas, perdendo o
vendedor e a categoria, que o formato expressa pela posição e não por coluna.

**Decisão.** O parser mantém `current_responsavel` e `current_artigo` durante a
máquina de estados e injeta ambos em cada linha extraída. A detecção é
insensível a maiúsculas e tolera ausência de acentos, para suportar variações
entre arquivos.

**Consequência.** Toda venda passou a ser analisável por vendedor e por
categoria. Algumas vendas têm responsável vazio — é o ERP sem vendedor
atribuído, e o pipeline preserva essa ausência em vez de inventar um valor.

---

## D-007 — Chaves de negócio com separador explícito

**Contexto.** As chaves eram concatenações diretas:
`001` + `001-100000` + `2025-09-08` = `001001-1000002025-09-08`.

O resultado é ilegível, não permite recuperar os componentes e é ambíguo: não
há como saber onde termina o número do documento e começa a data.

Além disso, `tipo_documento` é derivado do prefixo de `numero_documento` — o
parser o obtém fazendo `split("-")` sobre o próprio número. Incluí-lo na chave
duplicava informação que já estava lá.

**Decisão.** A chave usa `|` como separador, começa pelo sistema de origem e
dispensa o componente derivado:

```text
id_venda      = sistema | numero_documento | data    ATUAL|001-100000|2025-09-08
id_item_venda = id_venda | protocolo                 ATUAL|001-100000|2025-09-08|334053
```

Datas ausentes produzem `SEM_DATA` no lugar do componente, em vez de `None` ou
`NaT` serializados como texto.

**Consequência.** Mudança de contrato: as chaves geradas antes desta decisão
não são comparáveis com as atuais. `tipo_documento` continua publicado como
coluna — é a série do documento, tem valor analítico —, mas não participa da
identidade do registro.

---

## D-008 — Schema canônico único para as saídas

**Contexto.** A exportação despejava o DataFrame inteiro, com tudo o que as
etapas intermediárias tivessem acumulado. O resultado carregava a coluna
`produto` (que é exatamente `codigo_produto` + `" - "` + `descricao_produto`,
ambos já publicados) e serializava a data como texto, o que obriga a um `CAST`
em toda consulta que filtre por período.

**Decisão.** Uma única definição em `src/export/schema.py` estabelece colunas,
ordem e tipos. Parquet e CSV derivam dela, e por isso descrevem o mesmo
contrato. Colunas intermediárias são descartadas na publicação; colunas
ausentes na origem são criadas vazias, para que o contrato seja estável.

**Consequência.** O consumidor do dado tem uma referência única. A data vai
como tipo temporal nativo, e `WHERE data_emissao >= DATE '2025-01-01'` funciona
sem conversão.

---

## D-009 — Unicidade validada no item, não na venda

**Contexto.** A validação acusava erro quando `id_venda` se repetia. Só que a
granularidade do dado é o item da nota: uma venda com quatro produtos produz
quatro linhas com o mesmo `id_venda`.

A regra transformava o comportamento normal da operação em erro de validação.

**Decisão.** A unicidade é verificada em `id_item_venda`, a chave primária real
do dataset. `id_venda` é explicitamente 1:N.

**Consequência.** A validação passou a refletir o negócio. A contagem de vendas
continua sendo `COUNT(DISTINCT id_venda)`, e a consulta `itens-por-nota` expõe
essa distribuição diretamente.

---

## D-010 — Dados sintéticos como parte do projeto

**Contexto.** Com `data/` fora do versionamento, os parsers do sistema legado
não tinham como ser executados por quem não tivesse os arquivos originais. Na
prática, a parte mais difícil do projeto era a menos verificável.

**Decisão.** O módulo `demo` gera arquivos nos formatos de origem: o XLSX
hierárquico e os três `.rel` de largura fixa — reproduzindo as 132 colunas, a
codificação latin-1, os números em formato brasileiro, os cabeçalhos de página
repetidos e as datas corrompidas com a sentinela `01/01/19`.

**Consequência.** Os parsers do legado passaram a ter testes de integração
reais. O CI executa o fluxo completo — gerar, processar, consultar — a cada
push. A geração é determinística por semente.

---

## D-011 — Parquet como formato principal, CSV sob demanda

**Contexto.** A saída anterior era um CSV gerado a cada execução, moldado para
uma ferramenta de BI específica. Isso fixava a decisão de consumo dentro do
pipeline e exigia serializar tudo como texto.

**Decisão.** O pipeline publica Parquet tipado e comprimido, consultável em SQL
local via DuckDB sem servidor e sem carga intermediária. O CSV padronizado
passou a ser opcional (`aldebaran run --csv`), para ferramentas de BI que não
leem Parquet.

**Consequência.** O dado publicado é analisável no mesmo comando em que é
gerado, e a escolha da ferramenta de visualização deixou de ser uma decisão do
pipeline.

---

## D-012 — Datas ausentes são aviso, não erro

**Contexto.** A migração de servidor de 2023 deixou vendas sem data de emissão.
Tratar isso como erro de validação levaria a descartar faturamento real; ignorar
o problema esconderia uma lacuna conhecida da origem.

**Decisão.** O relatório de validação separa `errors` (quebram o contrato) de
`warnings` (lacunas conhecidas que não invalidam o registro). Data ausente é
aviso: a linha permanece no dataset, sinalizada, e a chave registra `SEM_DATA`.

**Consequência.** Nenhuma venda é perdida por um defeito da origem, e a lacuna
fica visível no resumo da execução e no arquivo de auditoria.

---

## D-013 — Confiança declarada na reconstrução cronológica

**Contexto.** Nos `.rel` de compras, a data impressa é inconfiável e precisa ser
inferida a partir da sequência de CI. Uma data inferida apresentada como dado de
origem é pior do que uma data ausente: induz confiança indevida.

**Decisão.** Cada registro reconstruído carrega o nível de confiança da
inferência (`Alta`, `Média`, `Baixa`) e preserva a data original impressa em
`data_original`.

**Consequência.** Quem consome o histórico do legado pode filtrar por
confiança, e a inferência permanece auditável contra o que o relatório
realmente dizia.

---

## D-014 — Uma versão por item, resolvida pelo arquivo mais recente

**Contexto.** A consolidação removia apenas linhas idênticas. Um relatório
parcial e a sua versão consolidada diferindo por um centavo — arredondamento,
correção de valor — passavam as duas, e o faturamento daquela venda era contado
em dobro. É o cenário corriqueiro da operação: extração semanal com
reexportações do mesmo período.

A especificação já prometia "versão consolidada substitui a parcial"; o código
não implementava.

**Decisão, revista em 2026-09-16.** Depois da padronização,
`resolve_versoes` mantém uma única ocorrência de cada `id_item_venda`. A maior
data final de cobertura prevalece, independentemente do nome ou da ordem do
arquivo. Se duas versões de maior cobertura empatam com conteúdo diferente,
nenhuma ocorrência daquela identidade é publicada automaticamente: todas vão
para quarentena.

**Consequência.** O faturamento deixa de ser inflado por reprocessamento. A
ordem alfabética deixa de representar precedência. Empates são tratados de
forma conservadora, inclusive impedindo que uma versão antiga reapareça quando
as versões mais recentes estão em conflito. Cobertura derivada das próprias
vendas continua sendo metadado de confiança menor que um período declarado.

---

## D-015 — Colisão de chave por falta de data é desambiguada, não fundida

**Contexto.** Datas ausentes produzem `SEM_DATA` na chave (D-012). Dois
documentos de mesmo número e mesmo protocolo, ambos sem data, geravam a mesma
`id_item_venda`: duas vendas distintas colapsavam numa só identidade, e a base
saía com chave primária duplicada.

**Decisão.** A desambiguação se aplica **apenas** às linhas sem data. Cada
ocorrência além da primeira recebe um sufixo ordinal (`#2`, `#3`), e o total
aparece como aviso na validação.

Quando há data, a chave é confiável e uma colisão significa outra coisa — o
mesmo item exportado em dois relatórios. Esse caso é de versão, e cabe a D-014;
desambiguar ali esconderia a dupla contagem.

**Consequência.** Nenhuma venda é perdida por falta de data, e a chave primária
volta a ser única. Duas notas homônimas sem data ainda compartilham o
`id_venda` — a contagem de notas, nesse caso específico, é conservadora.

---

## D-016 — O ano reconstruído é validado contra o período do relatório

**Contexto.** A reconstrução do ano no analítico do legado impede que a série
retroceda: se o ano impresso é menor que o anterior, prevalece o anterior. Um
ano impresso corrompido para mais quebra esse método — num teste, trocar um
único dígito (`09` → `99`) empurrou 71% dos registros para 2099, porque a série
nunca desce.

Pior: o teste que existia verificava que o ano nunca decresce, propriedade que o
algoritmo garante por construção. Ele passava sobre a base destruída.

**Decisão.** O relatório declara no cabeçalho o período que cobre. O ano
candidato é validado contra esse intervalo; o que estiver fora é descartado em
favor do último ano válido, e o registro é marcado com `ano_suspeito`.

O gerador de dados sintéticos passou a injetar a anomalia que o algoritmo existe
para tratar — anos impressos regredidos — e a devolver o gabarito dos anos
reais, para que o teste compare a reconstrução com a verdade em vez de conferir
uma tautologia.

**Consequência.** Um valor corrompido fica contido no registro em que ocorre.
Os testes agora falham quando o algoritmo é desligado, o que foi verificado por
mutação.

---

## D-017 — Nem todo relatório do legado pode virar faturamento

**Contexto.** O pipeline publicava apenas o XLSX do sistema atual. Os parsers
do legado existiam, eram testados, e não eram chamados por ninguém: a
documentação prometia 25 anos de histórico e a base publicada cobria dois.

Integrar tudo indiscriminadamente seria pior. Os três `.rel` têm naturezas
diferentes: o analítico de vendas tem uma linha por item, com data e CI; o
sintético traz totais acumulados por item, sem data nem documento; o de compras
registra entradas, não saídas.

**Decisão.** `ingest_legado` reconhece o tipo de cada arquivo pelo cabeçalho e
pelo layout, ingere o analítico de vendas e declara o motivo de cada exclusão.
Cada linha publicada carrega `sistema_origem` (`ATUAL` ou `LEGADO`) e
`confianca_data`, distinguindo data lida de data inferida.

**Consequência.** A base publicada cobre de 2002 a 2026 e a afirmação dos 25
anos passou a ser verificável com `aldebaran query cobertura`. Somar o
sintético inventaria vendas que o relatório não descreve, e somar compras
inflaria a receita — por isso os dois ficam de fora, com o motivo impresso na
execução.

---

## D-018 — Dinheiro é canônico em centavos inteiros

**Contexto.** `float` binário é inadequado como contrato monetário: somas e
comparações podem acumular resíduos que não existem na moeda.

**Decisão.** A padronização converte o valor observado para
`valor_total_venda_centavos`, inteiro e obrigatório. O Parquet publica
centavos; a view SQL `vendas` expõe `valor_total_venda` em reais para manter a
consulta legível.

**Consequência.** Cálculos internos são exatos na menor unidade monetária. A
conversão para reais fica na borda de consumo, e a alteração é versionada como
schema `1.0.0`.

---

## D-019 — Registros inválidos são isolados, não misturados à publicação

**Contexto.** Interromper toda a carga por uma linha defeituosa apaga os dados
válidos; publicar tudo transfere silenciosamente o erro ao indicador.

**Decisão.** Falta de coluna obrigatória é erro estrutural e interrompe a
execução. Violações de linha são retiradas do dataset publicado e gravadas em
quarentena com código, motivo, registro observado e `id_execucao`. A execução
termina com status `PARCIAL`. Data ausente permanece aceita e sinalizada como
aviso, conforme D-012.

**Consequência.** O dado aproveitável continua disponível sem esconder perdas.
Uma linha inválida também não contamina uma linha válida apenas por carregar
uma chave derivada inconsistente.

---

## D-020 — Auditoria identificável e publicação preparada em staging

**Contexto.** O identificador existia nas linhas, mas não no arquivo de
auditoria; `execucao.json` era sobrescrito e não provava quais arquivos haviam
produzido o resultado. Além disso, o Parquet era substituído antes de a
auditoria e a quarentena terminarem.

**Decisão.** Parquet e auditoria compartilham `id_execucao`. A auditoria guarda
versões do pipeline e do schema, tamanho e SHA-256 de entradas e saídas. Cada
execução ganha um arquivo histórico, além do ponteiro corrente
`execucao.json`. Os artefatos são produzidos em staging e promovidos somente
depois que todos foram gerados; `execucao.json` é o marcador final.

**Consequência.** Uma falha tardia não substitui o Parquet anterior, e uma
linha publicada pode ser ligada a uma execução e aos bytes que ela consumiu.

---

## D-021 — Ausência e conversão inválida não significam zero

**Contexto.** Os parsers convertiam célula ausente ou texto numérico
malformado em `0.0`. Como zero é um valor comercial possível, a validação não
conseguia distinguir uma cortesia real de faturamento perdido por erro de
origem ou conversão.

**Decisão.** Zero só é publicado quando observado como zero. Ausência ou falha
de conversão permanece nula durante ingestão e padronização; sendo o valor
monetário obrigatório, o registro é isolado pela validação e segue para a
quarentena.

**Consequência.** Uma célula defeituosa deixa de reduzir faturamento
silenciosamente, sem impedir a publicação dos demais registros válidos.

---

## D-022 — Apenas candidatos válidos participam da precedência de versões

**Contexto.** Resolver versões antes de validar permitia que uma exportação
mais recente, porém inválida, substituísse a ocorrência válida anterior e fosse
depois rejeitada. O resultado era a perda das duas.

**Decisão.** A validação de elegibilidade por linha acontece antes da resolução
de versões, adiando apenas a regra de unicidade. A unicidade final é verificada
depois que a consolidação decide entre versões válidas da mesma identidade.

**Consequência.** Uma versão inválida segue para quarentena sem remover a
última versão válida conhecida do item.

---

## D-023 — Promoção coordenada restaura a publicação anterior

**Contexto.** Gerar todos os artefatos em staging evita falhas durante a
geração, mas não torna várias substituições de arquivo uma operação atômica.
Uma falha entre a troca do Parquet e a troca de `execucao.json` deixava
execuções diferentes visíveis como se fossem uma só.

**Decisão.** Cada destino existente recebe um backup no mesmo diretório antes
da promoção. Se qualquer troca falhar, os artefatos já promovidos são removidos
e todos os backups são restaurados. O marcador corrente continua sendo o último
arquivo promovido.

**Consequência.** Falhas tratáveis durante a promoção preservam o conjunto
anterior coerente. A garantia não pretende substituir transação de filesystem
diante de encerramento abrupto do processo ou da máquina.

---

## D-024 — Identidade derivada não depende da proveniência física

**Contexto.** Quando o protocolo faltava, a chave incorporava nome do arquivo
e número da linha. Renomear ou reordenar a mesma exportação mudava a identidade
e impedia reconhecer sua reexportação, permitindo dupla contagem.

**Decisão.** Na ausência de protocolo, o item recebe um token determinístico do
produto e a ocorrência desse produto dentro da venda e da fonte. Nome e linha
permanecem linhagem, nunca identidade. A mesma estratégia de ocorrência por
fonte evita que colisões sem data ganhem ordinais globais dependentes da ordem
de ingestão. O schema `1.1.0` publica `confianca_identidade`.

**Consequência.** Renomear o arquivo não altera a chave e reexportações podem
participar da regra de versões. Como a identidade ainda é inferida quando falta
protocolo ou data, essa limitação fica explícita para o consumidor.

---

## D-025 — O schema é validado e gravado fisicamente

**Contexto.** O contrato declarava nulabilidade, mas a exportação criava
colunas obrigatórias ausentes e convertia valores incoercíveis em nulo. O
retorno Python também expunha colunas intermediárias diferentes do Parquet.

**Decisão.** Campos obrigatórios ausentes, vazios ou incoercíveis interrompem a
exportação. O Parquet é escrito com schema PyArrow explícito, inclusive
nulabilidade, e `run_pipeline()["dados"]` devolve exatamente o DataFrame
canônico publicado. A mudança define o schema `1.2.0`.

**Consequência.** API Python, CSV e Parquet deixam de oferecer contratos
divergentes, e um valor incompatível não pode virar nulo silenciosamente na
borda de publicação.

---

## D-026 — Falhas também são execuções auditáveis

**Contexto.** A auditoria só era criada ao final do caminho bem-sucedido. Uma
falha estrutural ou operacional não deixava registro, a quarentena não tinha
fingerprint e a versão do pacote não identificava código local modificado.

**Decisão.** A execução passa a declarar `SUCESSO`, `PARCIAL` ou `FALHA`.
Falhas fatais preservam um registro histórico sem alterar o marcador da última
publicação válida. A auditoria registra a revisão Git com marca de estado sujo,
e todos os artefatos materiais, inclusive quarentena, entram nas saídas
fingerprintadas.

**Consequência.** Ausência de publicação deixa de significar ausência de
evidência, e uma execução parcial pode ser distinguida de falha total sem
inferir o estado a partir de mensagens livres.

---

## D-027 — Escala e visualização precisam de evidência reproduzível

**Contexto.** O caso real menciona volume elevado, mas o repositório público é
reduzido. Também faltava uma forma não técnica de inspecionar o resultado sem
acoplar o pipeline a uma ferramenta de BI.

**Decisão.** Um benchmark parametrizável mede apenas o núcleo tabular e declara
explicitamente que não cobre parsing. Uma visão HTML local consome somente o
Parquet publicado, trabalha com agregados, oferece filtro por sistema e não
introduz meta, previsão ou causalidade sem fonte.

**Consequência.** Desempenho deixa de ser alegação sem método, e gestores podem
examinar o resultado sem transformar a camada visual em regra de negócio ou
dependência do pipeline.
