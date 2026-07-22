# Aldebaran — leitura executiva

## Em uma frase

O Aldebaran transforma relatórios comerciais que só podiam ser lidos
manualmente em uma base histórica consultável, reproduzível e acompanhada de
evidências sobre a qualidade dos dados.

## Necessidade de negócio

O problema não era ausência de informação. O histórico existia, mas estava
preso em relatórios de impressão de dois sistemas, com estruturas e limitações
diferentes. Isso criava quatro custos operacionais:

- dependência recorrente da TI para preparar recortes;
- análises limitadas à janela que uma pessoa conseguia consolidar;
- risco de dupla contagem, exclusão ou interpretação incorreta;
- falta de evidência sobre como cada número havia sido produzido.

O projeto substitui esse processo por uma carga local repetível. Os números do
caso real descritos no README são contexto operacional; o repositório público
usa somente dados sintéticos e não tenta reproduzir resultados de uma empresa.

## O que passa a ser possível

| Necessidade | Capacidade entregue | Evidência pública |
|-------------|---------------------|-------------------|
| Consultar a série histórica | Dois sistemas publicados em uma base | `aldebaran query cobertura` |
| Observar sazonalidade | Datas tipadas e série mensal | `aldebaran query sazonalidade` |
| Entender concentração | Ranking por produto e responsável | consultas `top-produtos` e `responsaveis` |
| Confiar na procedência | Sistema e confiança da data por linha | `aldebaran query procedencia` |
| Evitar faturamento duplicado | Identidade no item e precedência por cobertura | testes de consolidação |
| Investigar perdas | Rejeitados isolados com código e motivo | Parquet de quarentena |
| Reproduzir uma execução | ID, versões e SHA-256 de entradas e saídas | `execucao.json` |

Essas capacidades apoiam decisões; não substituem a interpretação de quem
conhece a operação. Em especial, datas inferidas devem ser analisadas
separadamente quando a pergunta depende de precisão temporal.

## Controles que protegem o indicador

- A granularidade é declarada: uma linha representa um item, não uma venda.
- Compras e relatórios agregados não são tratados como faturamento.
- Data inferida não se confunde com data observada.
- Uma versão antiga não reaparece quando versões recentes estão em conflito.
- Falha de linha gera quarentena; falha estrutural interrompe a publicação.
- Uma falha tardia preserva o Parquet anteriormente publicado.

## O que o projeto demonstra tecnicamente

O valor técnico não está em usar muitas ferramentas. Está em transformar
restrições reais — sem banco de origem, formatos irregulares e regras
ambíguas — em contratos verificáveis. O repositório evidencia:

- parsing de XLSX hierárquico por máquina de estados;
- parsing de texto de largura fixa e codificação legada;
- modelagem de chaves e granularidade de negócio;
- dinheiro canônico em centavos inteiros;
- testes de contrato, integração e regressão;
- publicação Parquet, consulta DuckDB e auditoria por execução.

## Uso responsável de IA no desenvolvimento

O projeto foi organizado para que assistência de IA não substitua julgamento
humano. Mudanças de regra começam por um caso de teste, alterações de contrato
são registradas em `DECISIONS.md`, dados reais não entram no repositório e as
afirmações públicas precisam ser reproduzíveis com o conjunto sintético.

A IA pode acelerar investigação, geração de casos adversos e revisão, mas a
responsabilidade pelas regras de negócio, pela arquitetura e pela publicação
permanece humana. Esse processo é mais importante do que a ferramenta usada
para escrever cada linha.

## Limites honestos

- O pipeline é local e processa os dados em memória; não afirma escala
  distribuída sem benchmark que a justifique.
- Os adaptadores atendem aos layouts documentados, não a qualquer ERP.
- O repositório público comprova comportamento, não o volume do caso real.
- Visualização é uma camada consumidora; a base e suas regras permanecem
  independentes de uma ferramenta específica de BI.
