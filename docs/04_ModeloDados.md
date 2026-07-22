# Modelo de Dados

|  Campo               Tipo      Obrigatório  Origem
|  ------------------- --------- ------------ ----------------------
|  produto             texto     Sim          Coluna A do raw
|  data_emissao        data      Sim          Coluna H
|  tipo_documento      texto     Sim          Derivado da NF Nº
|  numero_documento    texto     Sim          Coluna J (NF Nº)
|  id_venda            texto     Sim          tipo_documento + numero_documento + data_emissao
|  protocolo           texto     Condicional  Coluna I
|  id_item_venda       texto     Condicional  id_venda + protocolo
|  valor_total_venda   decimal   Sim          Coluna N
|  quantidade          decimal   Não          Coluna G
|  unidade_medida      texto     Não          Coluna F
|  responsavel         texto     Sim          Linha "Responsável: NOME" (hierarquia do XLSX)
|  artigo              texto     Sim          Linha "Artigo: NOME" (categoria do produto)
