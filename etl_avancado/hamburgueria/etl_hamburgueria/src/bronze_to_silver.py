import pandas as pd
from sqlalchemy import text

from src.config import ensure_dw, get_postgres_engine
from src.utils import (
    agora, limpar_tabela, limpar_watermarks, ler_sql, obter_watermark,
    salvar_watermark, ultimo_timestamp, upsert_dataframe
)


def executar(modo="incremental"):
    engine = get_postgres_engine()
    ensure_dw(engine)

    if modo == "full":
        for tabela in ["produtos", "pedidos", "itens_pedido"]:
            limpar_tabela(engine, "silver", tabela)
        limpar_watermarks(engine, "silver")

    # Produtos: sem updated_at na origem, processamos o histórico Bronze inteiro.
    produtos = ler_sql(engine, """
        SELECT DISTINCT ON (id_produto)
            id_produto, nome, categoria, preco, ativo
        FROM bronze.produtos
        ORDER BY id_produto, ts_load_bronze DESC
    """)
    produtos["ts_load_silver"] = agora()
    upsert_dataframe(engine, "silver", "produtos", produtos, "id_produto")

    watermark_pedidos = obter_watermark(engine, "silver", "pedidos")
    watermark_itens = obter_watermark(engine, "silver", "itens_pedido")

    if modo == "full" or watermark_pedidos is None:
        pedidos = ler_sql(engine, "SELECT * FROM bronze.pedidos")
    else:
        pedidos = ler_sql(engine, """
            SELECT * FROM bronze.pedidos
            WHERE updated_at > :watermark
        """, {"watermark": watermark_pedidos})

    if not pedidos.empty:
        pedidos = (
            pedidos.sort_values(["updated_at", "ts_load_bronze"])
            .drop_duplicates("id_pedido", keep="last")
        )
        pedidos_silver = pedidos.drop(columns=["ts_load_bronze"])
        pedidos_silver["ts_load_silver"] = agora()
        upsert_dataframe(engine, "silver", "pedidos", pedidos_silver, "id_pedido")
        salvar_watermark(
            engine, "silver", "pedidos", ultimo_timestamp(pedidos)
        )

    if modo == "full" or watermark_itens is None:
        itens = ler_sql(engine, "SELECT * FROM bronze.itens_pedido")
    else:
        itens = ler_sql(engine, """
            SELECT * FROM bronze.itens_pedido
            WHERE updated_at > :watermark
        """, {"watermark": watermark_itens})

    if not itens.empty:
        # Para cada pedido alterado, considera somente a última fotografia de itens.
        ultima_versao = itens.groupby("id_pedido")["updated_at"].transform("max")
        itens = itens[itens["updated_at"] == ultima_versao].copy()

        pedidos_alterados = itens["id_pedido"].dropna().unique().tolist()

        # A aplicação substitui os itens ao editar um pedido.
        # Excluímos os itens anteriores daquele pedido e gravamos sua versão atual.
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM silver.itens_pedido WHERE id_pedido = ANY(:ids)"),
                {"ids": pedidos_alterados}
            )

        itens_silver = itens.drop(columns=["ts_load_bronze"])
        itens_silver["ts_load_silver"] = agora()
        itens_silver = itens_silver.drop_duplicates("id_item", keep="last")
        upsert_dataframe(engine, "silver", "itens_pedido", itens_silver, "id_item")
        salvar_watermark(
            engine, "silver", "itens_pedido", ultimo_timestamp(itens)
        )

    print(
        f"Silver concluída | produtos: {len(produtos)} | "
        f"pedidos: {len(pedidos)} | itens: {len(itens)}"
    )


if __name__ == "__main__":
    executar("incremental")
    