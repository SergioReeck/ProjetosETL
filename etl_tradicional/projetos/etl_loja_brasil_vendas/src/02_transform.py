import pandas as pd
from utils import gravar_dados, importar_modulo

config = importar_modulo("00_config.py", "config")

engine_dw = config.engine_dw


def transformacao_silver():
    print("Iniciando processamento (transformação) da Silver...")

    # ========================================
    # Leitura da Bronze para DataFrames
    # ========================================
    
    df_vendas = pd.read_sql(
        "SELECT * FROM bronze.loja_brasil_vendas",
        engine_dw
    )

    df_clientes = pd.read_sql(
        "SELECT * FROM bronze.loja_brasil_clientes",
        engine_dw
    )

    df_municipios = pd.read_sql(
        "SELECT cidade, estado, mesorregiao FROM bronze.api_ibge_municipios",
        engine_dw
    )

    df_produtos = pd.read_sql(
        "SELECT * FROM bronze.loja_brasil_produtos",
        engine_dw
    )

    df_vendedores = pd.read_sql(
        "SELECT * FROM bronze.loja_brasil_vendedores",
        engine_dw
    )
    
    print("Captura de dados da Bronze para DataFrames concluída.")

    # ========================================
    # Transformações e limpeza de dados
    # ========================================

    # Conversão de datas
    df_vendas["data_pedido"] = pd.to_datetime(df_vendas["data_pedido"])

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
    df_clientes["cidade"] = df_clientes["cidade"].str.strip()
    df_clientes["estado"] = df_clientes["estado"].str.upper()

    df_municipios["cidade"] = df_municipios["cidade"].str.strip()
    df_municipios["estado"] = df_municipios["estado"].str.upper()

    df_clientes = df_clientes.merge(
        df_municipios[["cidade", "estado", "mesorregiao"]],
        on=["cidade", "estado"],
        how="left"    
    )

    # ========================================
    # Gravando dados na camada Silver
    # ========================================
    
    tabelas = {
            "vendas": (df_vendas, "loja_brasil_vendas"),
            "clientes": (df_clientes, "loja_brasil_clientes"),
            "produtos": (df_produtos, "loja_brasil_produtos"),
            "vendedores": (df_vendedores, "loja_brasil_vendedores"),
    }
    
    camada = "silver"
    
    for nome, (df, nome_tabela) in tabelas.items():
        print(f"Gravando dados da tabela silver.{nome}")
        gravar_dados(df, nome_tabela, engine_dw, camada)

    print("Silver carregada.")
