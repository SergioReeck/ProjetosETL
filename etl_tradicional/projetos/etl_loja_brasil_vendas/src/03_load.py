import pandas as pd
from config import engine_dw

def processar_gold():
    print("Processando camada Gold (Load)...")

    # ========================================
    # Leitura da Silver para DataFrames
    # ========================================

    df_vendas = pd.read_sql(
        "SELECT * FROM silver.vendas_tratadas",
        engine_dw
    )

    df_ibge = pd.read_sql(
        "SELECT * FROM silver.municipios",
        engine_dw
    )

    df_metas = pd.read_sql(
        "SELECT * FROM silver.metas_vendas",
        engine_dw
    )

    # ========================================
    # Criação de DataFrames analíticos
    # ========================================

    df_fato = df_vendas[
        [
            "id_pedido", "data_pedido", "id_cliente", "cliente",
            "cidade", "estado", "id_ibge", "id_produto",
            "produto", "categoria", "marca", "quantidade",
            "preco_unitario", "desconto", "valor_item"
        ]
    ].copy()

    df_municipios = df_ibge[
        [
            "id_ibge", "cidade", "estado", "regiao",
            "mesorregiao", "microrregiao",
            "regiao_imediata", "regiao_intermediaria"
        ]
    ].copy()

    df_resumo = (
        df_vendas
        .groupby(
            ["ano", "mes", "estado", "meta_vendas"],
            as_index=False
        )["valor_item"]
        .sum()
        .rename(columns={"valor_item": "vendas_realizadas"})
    )

    df_resumo["percentual_atingimento"] = (
        df_resumo["vendas_realizadas"]
        / df_resumo["meta_vendas"]
        * 100
    ).round(2)

    df_resumo["situacao_meta"] = df_resumo[
        "percentual_atingimento"
    ].apply(
        lambda x: "Meta atingida" if x >= 100 else "Meta não atingida"
    )

    # ========================================
    # Carregando dos DataFrames na camada Gold
    # ========================================

    df_fato.to_sql(
        "fato_vendas", engine_dw,
        schema="gold", if_exists="replace", index=False
    )

    df_municipios.to_sql(
        "dim_municipios", engine_dw,
        schema="gold", if_exists="replace", index=False
    )

    df_metas.to_sql(
        "metas_vendas", engine_dw,
        schema="gold", if_exists="replace", index=False
    )

    df_resumo.to_sql(
        "fato_metas_mensais", engine_dw,
        schema="gold", if_exists="replace", index=False
    )

    print("Gold carregada.")