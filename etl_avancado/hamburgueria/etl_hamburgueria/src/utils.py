from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import MetaData, Table, text
from sqlalchemy.dialects.postgresql import insert as pg_insert


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ler_sql(engine, query, params=None):
    return pd.read_sql(text(query), engine, params=params or {})


def obter_watermark(engine, camada, tabela):
    query = text("""
        SELECT ultimo_updated_at
        FROM public.etl_controle
        WHERE camada = :camada AND tabela = :tabela
    """)
    with engine.connect() as conn:
        return conn.execute(
            query, {"camada": camada, "tabela": tabela}
        ).scalar()


def salvar_watermark(engine, camada, tabela, valor):
    if valor is None or pd.isna(valor):
        return

    query = text("""
        INSERT INTO public.etl_controle
            (camada, tabela, ultimo_updated_at)
        VALUES (:camada, :tabela, :valor)
        ON CONFLICT (camada, tabela)
        DO UPDATE SET ultimo_updated_at = EXCLUDED.ultimo_updated_at
    """)
    with engine.begin() as conn:
        conn.execute(query, {
            "camada": camada,
            "tabela": tabela,
            "valor": valor
        })


def limpar_tabela(engine, schema, tabela):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {schema}.{tabela}"))


def limpar_watermarks(engine, camada):
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM public.etl_controle
            WHERE camada = :camada
        """), {"camada": camada})


def upsert_dataframe(engine, schema, tabela, df, chave):
    """Insere novos registros e atualiza os existentes pela chave informada."""
    if df.empty:
        return

    metadata = MetaData()
    destino = Table(tabela, metadata, schema=schema, autoload_with=engine)

    registros = df.astype(object).where(pd.notna(df), None).to_dict("records")
    comando = pg_insert(destino).values(registros)

    colunas_atualizar = {
        coluna.name: comando.excluded[coluna.name]
        for coluna in destino.columns
        if coluna.name != chave
    }

    comando = comando.on_conflict_do_update(
        index_elements=[destino.c[chave]],
        set_=colunas_atualizar
    )

    with engine.begin() as conn:
        conn.execute(comando)


def ultimo_timestamp(df, coluna="updated_at"):
    if df.empty or coluna not in df.columns:
        return None
    datas = pd.to_datetime(df[coluna], errors="coerce")
    if datas.notna().sum() == 0:
        return None
    indice = datas.idxmax()
    # Mantém o texto ISO original para comparar corretamente com o SQLite.
    return str(df.loc[indice, coluna])
