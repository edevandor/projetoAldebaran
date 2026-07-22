# Regras de Negócio

## Venda

-   id_venda = tipo_documento + numero_documento + data_emissao
-   Contagem de vendas = COUNT DISTINCT(id_venda)

## Itens

-   id_item_venda = id_venda + protocolo

## Datas

-   Data oficial = Data Emissão

## Calendário

-   Segunda a sábado operacionais.
-   Domingo não operacional.
-   Feriados não recebem tratamento especial.

## Arquivos

-   Versão consolidada substitui parcial.
-   Nunca duplicar períodos.
