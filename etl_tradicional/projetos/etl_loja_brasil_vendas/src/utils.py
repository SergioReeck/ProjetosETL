import importlib.util
from pathlib import Path

import pandas as pd


def importar_modulo(nome_arquivo, nome_modulo):
    caminho = Path(__file__).parent / nome_arquivo

    spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    return modulo


def extrair_dados(query_sql, conexao):
    return pd.read_sql(query_sql, conexao)


def gravar_bronze(df, nome_tabela, conexao):
    df.to_sql(
        nome_tabela,
        conexao,
        schema="bronze",
        if_exists="replace",
        index=False,
    )
