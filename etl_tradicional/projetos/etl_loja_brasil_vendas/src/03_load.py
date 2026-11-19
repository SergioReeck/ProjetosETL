import pandas as pd
from utils import gerar_dim_calendario, gravar_dados, importar_modulo

config = importar_modulo("00_config.py", "config")

engine_dw = config.engine_dw


def processar_gold():
    print("Processando camada Gold (Load)...")

    # ========================================
    # Leitura da Silver para DataFrames
    # ========================================

    df_vendas = pd.read_sql(
        "SELECT * FROM silver.loja_brasil_vendas",
        engine_dw
    )

    df_clientes = pd.read_sql(
        "SELECT * FROM silver.loja_brasil_clientes",
        engine_dw
    )

    df_produtos = pd.read_sql(
        "SELECT * FROM silver.loja_brasil_produtos",
        engine_dw
    )

    df_vendedores = pd.read_sql(
        "SELECT * FROM silver.loja_brasil_vendedores",
        engine_dw
    )

    # ========================================
    # Enriquecimento de datas
    # ========================================

    df_vendas["data_pedido"] = pd.to_datetime(df_vendas["data_pedido"]).dt.normalize()
    data_inicio = df_vendas["data_pedido"].min()
    data_fim = df_vendas["data_pedido"].max()

    # Gerar dimensão calendário
    df_calendario = gerar_dim_calendario(data_inicio, data_fim)

    # Vincular a dimensão calendário com a tabela de vendas
    df_vendas["sk_data"] = df_vendas["data_pedido"].dt.strftime("%Y%m%d").astype("int64")

    df_vendas = df_vendas.drop(columns=["data_pedido"])

    # ========================================
    # Criação de DataFrames fatos e dimensões
    # ========================================

    df_fato = df_vendas[
        [
            "id_pedido", "id_produto", "id_cliente", "sk_data",
            "id_vendedor", "quantidade", "preco_unitario", "desconto", "valor_item"
        ]
    ].copy()

    # ========================================
    # Carregando dados na camada Gold
    # ========================================

    tabelas = {
        "vendas": (df_fato, "fato_vendas"),
        "clientes": (df_clientes, "dim_clientes"),
        "produtos": (df_produtos, "dim_produtos"),
        "vendedores": (df_vendedores, "dim_vendedores"),
        "calendario": (df_calendario, "dim_calendario")
    }
        
    camada = "gold"
        
    for nome, (df, nome_tabela) in tabelas.items():
        print(f"Gravando dados da tabela gold.{nome}")
        gravar_dados(df, nome_tabela, engine_dw, camada)
    
    print("Gold carregada.")
    