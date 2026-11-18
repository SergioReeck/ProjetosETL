import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

# Banco ERP
engine_erp = create_engine(
    f"postgresql+psycopg2://"
    f"{os.getenv('ERP_USUARIO')}:{os.getenv('ERP_SENHA')}"
    f"@{os.getenv('ERP_HOST')}:{os.getenv('ERP_PORTA')}"
    f"/{os.getenv('ERP_BANCO')}"
) # "postgresql+psycopg2://usuario:senha@local:5432/banco_de_dados"

# Banco DW
engine_dw = create_engine(
    f"postgresql+psycopg2://"
    f"{os.getenv('DW_USUARIO')}:{os.getenv('DW_SENHA')}"
   f"@{os.getenv('DW_HOST')}:{os.getenv('DW_PORTA')}"
    f"/{os.getenv('DW_BANCO')}"
) # "postgresql+psycopg2://usuario:senha@local:5432/banco_de_dados"
