import pandas as pd
from config import engine_dw

def processar_silver():
    print("Iniciando processamento (transformação) da Silver...")

    # ========================================
    # Leitura da Bronze para DataFrames
    # ========================================
    
    df_vendas = pd.read_sql(
        "SELECT * FROM bronze.erp_vendas",
        engine_dw
    )

    df_ibge = pd.read_sql(
        "SELECT * FROM bronze.ibge_municipios",
        engine_dw
    )

    df_metas = pd.read_sql(
        "SELECT * FROM bronze.metas_vendas",
        engine_dw
    )


    print("Captura de dados da Bronze para DataFrames concluída.")

    # ========================================
    # Transformações e limpeza de dados
    # ========================================

    # Conversão de datas
    df_vendas["data_pedido"] = pd.to_datetime(df_vendas["data_pedido"])
    df_vendas["ano"] = df_vendas["data_pedido"].dt.year
    df_vendas["mes"] = df_vendas["data_pedido"].dt.month

    # Cálculos
    df_vendas["valor_item"] = (
        df_vendas["quantidade"]
        * df_vendas["preco_unitario"]
        * (1 - df_vendas["desconto"] / 100)
    ).round(2)

    # Remover pedidos cancelados
    df_vendas = df_vendas[
        df_vendas["status_pedido"] != "Cancelado"
    ].copy()

    # Padronização
    df_vendas["cidade"] = df_vendas["cidade"].str.strip()
    df_ibge["cidade"] = df_ibge["cidade"].str.strip()

    df_vendas["estado"] = df_vendas["estado"].str.upper()
    df_ibge["estado"] = df_ibge["estado"].str.upper()


    # ========================================
    # União de DataFrames
    # ========================================
    
    df_vendas = df_vendas.merge(
        df_ibge,
        on=["cidade", "estado"],
        how="left"
    )

    df_vendas = df_vendas.merge(
        df_metas,
        on=["ano", "mes", "estado"],
        how="left"
    )

    # Validações
    print("Sem correspondência IBGE:",
        df_vendas["id_ibge"].isna().sum())
    print("Sem correspondência de meta:",
        df_vendas["meta_vendas"].isna().sum())

    # ========================================
    # Gravando vendas_tratadas na camada Silver
    # ========================================
    df_vendas.to_sql(
        "vendas_tratadas",
        engine_dw,
        schema="silver",
        if_exists="replace",
        index=False
    )

    # ========================================
    # Gravando municipios na camada Silver
    # ========================================
    df_ibge.to_sql(
        "municipios",
        engine_dw,
        schema="silver",
        if_exists="replace",
        index=False
    )

    # ========================================
    # Gravando metas_vendas na camada Silver
    # ========================================
    df_metas.to_sql(
        "metas_vendas",
        engine_dw,
        schema="silver",
        if_exists="replace",
        index=False
    )

    print("Silver carregada.")