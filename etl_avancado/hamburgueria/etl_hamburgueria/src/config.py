import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def get_sqlite_engine():
    db_path = os.getenv("SQLITE_PATH", "../app_hamburgueria/data/hamburgueria.db")
    path = Path(db_path)
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Banco SQLite não encontrado: {path}\n"
            "Confira SQLITE_PATH no arquivo .env."
        )

    return create_engine(f"sqlite:///{path.as_posix()}")


def get_postgres_engine():
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    database = os.getenv("PG_DATABASE", "dw_hamburgueria")
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "")

    url = (
        f"postgresql+psycopg2://{user}:{password}"
        f"@{host}:{port}/{database}"
    )
    return create_engine(url)

def ensure_dw(engine):
    """Cria schemas, tabelas analíticas e tabela de controle, se necessário."""
    commands = [
        "CREATE SCHEMA IF NOT EXISTS bronze",
        "CREATE SCHEMA IF NOT EXISTS silver",
        "CREATE SCHEMA IF NOT EXISTS gold",

        """
        CREATE TABLE IF NOT EXISTS public.etl_controle (
            camada VARCHAR(20) NOT NULL,
            tabela VARCHAR(50) NOT NULL,
            ultimo_updated_at TEXT,
            PRIMARY KEY (camada, tabela)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS bronze.produtos (
            id_produto INTEGER,
            nome TEXT,
            categoria TEXT,
            preco NUMERIC(12,2),
            ativo INTEGER,
            ts_load_bronze TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS bronze.pedidos (
            id_pedido INTEGER,
            origem_pedido TEXT,
            tipo_atendimento TEXT,
            mesa TEXT,
            status TEXT,
            observacao TEXT,
            valor_total NUMERIC(12,2),
            created_at TEXT,
            updated_at TEXT,
            ts_load_bronze TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS bronze.itens_pedido (
            id_item INTEGER,
            id_pedido INTEGER,
            id_produto INTEGER,
            quantidade INTEGER,
            preco_unitario NUMERIC(12,2),
            subtotal NUMERIC(12,2),
            updated_at TEXT,
            ts_load_bronze TIMESTAMP NOT NULL
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS silver.produtos (
            id_produto INTEGER PRIMARY KEY,
            nome TEXT,
            categoria TEXT,
            preco NUMERIC(12,2),
            ativo INTEGER,
            ts_load_silver TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS silver.pedidos (
            id_pedido INTEGER PRIMARY KEY,
            origem_pedido TEXT,
            tipo_atendimento TEXT,
            mesa TEXT,
            status TEXT,
            observacao TEXT,
            valor_total NUMERIC(12,2),
            created_at TEXT,
            updated_at TEXT,
            ts_load_silver TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS silver.itens_pedido (
            id_item INTEGER PRIMARY KEY,
            id_pedido INTEGER,
            id_produto INTEGER,
            quantidade INTEGER,
            preco_unitario NUMERIC(12,2),
            subtotal NUMERIC(12,2),
            updated_at TEXT,
            ts_load_silver TIMESTAMP NOT NULL
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS gold.dim_produto (
            id_produto INTEGER PRIMARY KEY,
            nome TEXT,
            categoria TEXT,
            preco NUMERIC(12,2),
            ativo INTEGER,
            ts_load_gold TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS gold.fato_pedido_item (
            id_item INTEGER PRIMARY KEY,
            id_pedido INTEGER,
            id_produto INTEGER,
            origem_pedido TEXT,
            tipo_atendimento TEXT,
            mesa TEXT,
            status TEXT,
            quantidade INTEGER,
            preco_unitario NUMERIC(12,2),
            subtotal NUMERIC(12,2),
            created_at TEXT,
            updated_at TEXT,
            ts_load_gold TIMESTAMP NOT NULL
        )
        """
    ]

    with engine.begin() as conn:
        for command in commands:
            conn.execute(text(command))
            