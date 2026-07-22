"""Testes do módulo de consolidação — deduplicação de dados."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from consolidation.consolidator import consolidate


class TestConsolidate:
    """Suite de testes para a consolidação/deduplicação."""

    def _df_base(self) -> pd.DataFrame:
        """DataFrame com 3 linhas: 2 itens diferentes na mesma NF."""
        return pd.DataFrame([
            {
                "codigo_produto": "0000001", "descricao_produto": "FERRAMENTA A 150MM",
                "id_venda": "001001-1000012025-01-15", "id_item_venda": "001001-1000012025-01-15794925",
                "data_emissao": date(2025, 1, 15), "tipo_documento": "001",
                "numero_documento": "001-100001", "protocolo": "794925",
                "valor_total_venda": 150.0, "quantidade": 2, "unidade_medida": "UN",
                "produto": "0000001 - FERRAMENTA A 150MM",
                "arquivo_origem": "q1.xlsx",
            },
            {
                "codigo_produto": "0000002", "descricao_produto": "FERRAMENTA B 200MM",
                "id_venda": "001001-1000012025-01-15", "id_item_venda": "001001-1000012025-01-15794925",
                "data_emissao": date(2025, 1, 15), "tipo_documento": "001",
                "numero_documento": "001-100001", "protocolo": "794925",
                "valor_total_venda": 300.0, "quantidade": 1, "unidade_medida": "UN",
                "produto": "0000002 - FERRAMENTA B 200MM",
                "arquivo_origem": "q1.xlsx",
            },
            {
                "codigo_produto": "0000001", "descricao_produto": "FERRAMENTA A 150MM",
                "id_venda": "001001-1000012025-01-15", "id_item_venda": "001001-1000012025-01-15794925",
                "data_emissao": date(2025, 1, 15), "tipo_documento": "001",
                "numero_documento": "001-100001", "protocolo": "794925",
                "valor_total_venda": 150.0, "quantidade": 2, "unidade_medida": "UN",
                "produto": "0000001 - FERRAMENTA A 150MM",
                "arquivo_origem": "q2.xlsx",
            },
        ])

    def test_itens_diferentes_mantem_todos(self):
        """Dois itens diferentes na mesma NF não são removidos."""
        df = self._df_base()
        # Remove a duplicata (linha 3) deixando só as 2 primeiras
        df_sem_dup = df.drop(2).reset_index(drop=True)
        resultado, relatorio = consolidate(df_sem_dup)
        assert len(resultado) == 2
        assert relatorio["linhas_removidas"] == 0

    def test_linha_identica_entre_ficheiros_remove(self):
        """Mesmo item no Q1 e Q2 com todos os dados iguais é removido."""
        df = self._df_base()
        resultado, relatorio = consolidate(df)
        # Linha 0 e 2 são iguais (exceto arquivo_origem) → 1 removida
        assert len(resultado) == 2, f"Esperado 2, obtido {len(resultado)}"
        assert relatorio["linhas_removidas"] == 1

    def test_valores_diferentes_mantem(self):
        """Mesmo produto com valores diferentes mantém ambas."""
        df = self._df_base()
        # Linha 0: qtd=2, valor=150
        # Linha 2: modificar qtd para 3
        df.loc[2, "quantidade"] = 3
        df.loc[2, "valor_total_venda"] = 225.0
        resultado, relatorio = consolidate(df)
        assert len(resultado) == 3
        assert relatorio["linhas_removidas"] == 0

    def test_linha_exata_no_mesmo_arquivo_remove(self):
        """Linha duplicada exata no mesmo ficheiro é removida."""
        df = self._df_base()
        # Linha 3 = cópia exata da linha 0
        df3 = df.iloc[[0]].copy()
        df_com_dup = pd.concat([df, df3], ignore_index=True)
        resultado, relatorio = consolidate(df_com_dup)
        assert len(resultado) == 2
        assert relatorio["linhas_removidas"] == 2  # 1 cross-file + 1 same-file

    def test_relatorio_tem_metricas(self):
        """Relatório tem total_original, total_final, linhas_removidas."""
        df = self._df_base()
        _, relatorio = consolidate(df)
        assert relatorio["total_original"] == 3
        assert relatorio["total_final"] == 2
        assert relatorio["linhas_removidas"] == 1
