from sqlalchemy import text

from src.config import ensure_dw, get_postgres_engine
from src.utils import (
    agora, limpar_tabela, limpar_watermarks, obter_watermark,
    salvar_watermark, ultimo_timestamp, upsert_dataframe, ler_sql
)


def executar(modo="incremental"):
    engine = get_postgres_engine()
    ensure_dw(engine)

    if modo == "full":
        limpar_tabela(engine, "gold", "fato_pedido_item")
        limpar_tabela(engine, "gold", "dim_produto")
        limpar_watermarks(engine, "gold")

    # Dimensão: UPSERT por produto.
    produtos = ler_sql(engine, """
        SELECT id_produto, nome, categoria, preco, ativo
        FROM silver.produtos
    """)
    produtos["ts_load_gold"] = agora()
    upsert_dataframe(engine, "gold", "dim_produto", produtos, "id_produto")

    watermark = obter_watermark(engine, "gold", "pedidos")

    if modo == "full" or watermark is None:
        pedidos_alterados = ler_sql(engine, """
            SELECT id_pedido, updated_at
            FROM silver.pedidos
        """)
    else:
        pedidos_alterados = ler_sql(engine, """
            SELECT id_pedido, updated_at
            FROM silver.pedidos
            WHERE updated_at > :watermark
        """, {"watermark": watermark})

    if pedidos_alterados.empty:
        print("Gold concluída | nenhum pedido novo ou alterado.")
        return

    ids = pedidos_alterados["id_pedido"].dropna().tolist()

    # Atualiza a fotografia completa dos itens dos pedidos modificados.
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM gold.fato_pedido_item WHERE id_pedido = ANY(:ids)"),
            {"ids": ids}
        )

    fato = ler_sql(engine, """
        SELECT
            i.id_item,
            p.id_pedido,
            i.id_produto,
            p.origem_pedido,
            p.tipo_atendimento,
            p.mesa,
            p.status,
            i.quantidade,
            i.preco_unitario,
            i.subtotal,
            p.created_at,
            p.updated_at
        FROM silver.itens_pedido i
        JOIN silver.pedidos p ON p.id_pedido = i.id_pedido
        WHERE p.id_pedido = ANY(:ids)
    """, {"ids": ids})

    if not fato.empty:
        fato["ts_load_gold"] = agora()
        upsert_dataframe(engine, "gold", "fato_pedido_item", fato, "id_item")

    salvar_watermark(
        engine, "gold", "pedidos", ultimo_timestamp(pedidos_alterados)
    )

    print(
        f"Gold concluída | dimensões: {len(produtos)} | "
        f"pedidos atualizados: {len(ids)} | itens na fato: {len(fato)}"
    )


if __name__ == "__main__":
    executar("incremental")
    