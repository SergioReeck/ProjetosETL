import pandas as pd

from src.config import ensure_dw, get_postgres_engine, get_sqlite_engine
from src.utils import (
    agora, limpar_tabela, limpar_watermarks, obter_watermark,
    salvar_watermark, ultimo_timestamp
)


def executar(modo="incremental"):
    origem = get_sqlite_engine()
    destino = get_postgres_engine()
    ensure_dw(destino)

    if modo == "full":
        for tabela in ["produtos", "pedidos", "itens_pedido"]:
            limpar_tabela(destino, "bronze", tabela)
        limpar_watermarks(destino, "bronze")

    # Produtos não possuem updated_at na aplicação.
    # Como a tabela é pequena, lemos todos e deixamos a Silver consolidar por ID.
    produtos = pd.read_sql("SELECT * FROM produtos", origem)

    watermark_pedidos = obter_watermark(destino, "bronze", "pedidos")
    watermark_itens = obter_watermark(destino, "bronze", "itens_pedido")

    if modo == "full" or watermark_pedidos is None:
        pedidos = pd.read_sql("SELECT * FROM pedidos", origem)
    else:
        pedidos = pd.read_sql(
            "SELECT * FROM pedidos WHERE updated_at > :watermark",
            origem,
            params={"watermark": str(watermark_pedidos)}
        )

    if modo == "full" or watermark_itens is None:
        itens = pd.read_sql("""
            SELECT i.*, p.updated_at
            FROM itens_pedido i
            JOIN pedidos p ON p.id_pedido = i.id_pedido
        """, origem)
    else:
        itens = pd.read_sql("""
            SELECT i.*, p.updated_at
            FROM itens_pedido i
            JOIN pedidos p ON p.id_pedido = i.id_pedido
            WHERE p.updated_at > :watermark
        """, origem, params={"watermark": str(watermark_itens)})

    carregado_em = agora()
    produtos["ts_load_bronze"] = carregado_em
    pedidos["ts_load_bronze"] = carregado_em
    itens["ts_load_bronze"] = carregado_em

    produtos.to_sql("produtos", destino, schema="bronze", if_exists="append", index=False)
    pedidos.to_sql("pedidos", destino, schema="bronze", if_exists="append", index=False)
    itens.to_sql("itens_pedido", destino, schema="bronze", if_exists="append", index=False)

    salvar_watermark(destino, "bronze", "pedidos", ultimo_timestamp(pedidos))
    salvar_watermark(destino, "bronze", "itens_pedido", ultimo_timestamp(itens))

    print(
        f"Bronze concluída | produtos: {len(produtos)} | "
        f"pedidos: {len(pedidos)} | itens: {len(itens)}"
    )


if __name__ == "__main__":
    executar("incremental")
    