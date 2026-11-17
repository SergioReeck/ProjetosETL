from sqlalchemy import text
from config import engine_erp, engine_dw

def testar_conexao(engine, nome):
    print(f"\nTestando conexão: {nome}")

    try:
        with engine.connect() as conn:
            resultado = conn.execute(text("SELECT 1"))
            print("Conexão OK:", resultado.scalar())

    except Exception as erro:
        print("Falha na conexão!")
        print("Tipo:", type(erro).__name__)
        print("Detalhes:", repr(erro))


testar_conexao(engine_erp, "ERP")
testar_conexao(engine_dw, "DATA WAREHOUSE")
