from sqlalchemy import text
from utils import importar_modulo

config = importar_modulo("00_config.py", "config")

engine_dw = config.engine_dw


def configurar_dw():
    print("Configurando o Data Warehouse...")

    with engine_dw.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS silver"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))

    print("Schemas do DW criados.")
