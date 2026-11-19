import importlib.util
from pathlib import Path

import pandas as pd


def importar_modulo(nome_arquivo, nome_modulo):
    caminho = Path(__file__).parent / nome_arquivo

    spec = importlib.util.spec_from_file_location(nome_modulo, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    return modulo


def ler_dados(query_sql, conexao):
    return pd.read_sql(query_sql, conexao)


def gravar_dados(df, nome_tabela, conexao, camada):
    df.to_sql(
        name=nome_tabela,
        con=conexao,
        schema=camada,
        if_exists="replace",
        index=False,
    )


def gerar_dim_calendario(data_inicio, data_fim):
    """
    Gera uma dimensão calendário com uma linha por dia.

    sk_data: formato YYYYMMDD.
    Exemplo: 2025-02-10 = 20250210.
    """

    # Garantir que as datas sejam datetime
    data_inicio = pd.to_datetime(data_inicio).normalize()
    data_fim = pd.to_datetime(data_fim).normalize()

    # Gerar todas as datas do intervalo
    datas = pd.date_range(
        start=data_inicio,
        end=data_fim,
        freq="D"
    )

    df_calendario = pd.DataFrame({
        "data": datas
    })

    # Chave substituta
    df_calendario["sk_data"] = (
        df_calendario["data"]
        .dt.strftime("%Y%m%d")
        .astype("int64")
    )

    # Atributos temporais
    df_calendario["dia"] = df_calendario["data"].dt.day
    df_calendario["mes"] = df_calendario["data"].dt.month
    df_calendario["ano"] = df_calendario["data"].dt.year

    meses = [
        "Janeiro", "Fevereiro", "Março", "Abril",
        "Maio", "Junho", "Julho", "Agosto",
        "Setembro", "Outubro", "Novembro", "Dezembro"
    ]

    dias_semana = [
        "Segunda-feira", "Terça-feira", "Quarta-feira",
        "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"
    ]

    df_calendario["desc_mes"] = (
        df_calendario["mes"].map(lambda x: meses[x - 1])
    )

    df_calendario["semana"] = (
        df_calendario["data"]
        .dt.isocalendar()
        .week
        .astype("int64")
    )

    df_calendario["desc_semana"] = (
        df_calendario["data"]
        .dt.weekday
        .map(lambda x: dias_semana[x])
    )

    # Agrupamentos temporais
    df_calendario["bimestre"] = (
        (df_calendario["mes"] - 1) // 2 + 1
    )

    df_calendario["semestre"] = (
        (df_calendario["mes"] - 1) // 6 + 1
    )

    df_calendario["trimestre"] = (
        df_calendario["data"].dt.quarter
    )

    # Organização das colunas
    df_calendario = df_calendario[
        [
            "sk_data",
            "data",
            "dia",
            "mes",
            "desc_mes",
            "ano",
            "semana",
            "desc_semana",
            "bimestre",
            "semestre",
            "trimestre"
        ]
    ]

    return df_calendario
