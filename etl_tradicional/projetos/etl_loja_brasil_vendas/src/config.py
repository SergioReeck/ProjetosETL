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

# import os
# from dotenv import load_dotenv
# from sqlalchemy import create_engine
# from sqlalchemy.engine import URL

# load_dotenv()

# # Banco ERP
# url_erp = URL.create(
#     drivername="postgresql+psycopg2",
#     username=os.getenv("ERP_USUARIO"),
#     password=os.getenv("ERP_SENHA"),
#     host=os.getenv("ERP_HOST"),
#     port=int(os.getenv("ERP_PORTA")),
#     database=os.getenv("ERP_BANCO")
# )

# engine_erp = create_engine(url_erp)

# # Banco Data Warehouse
# url_dw = URL.create(
#     drivername="postgresql+psycopg2",
#     username=os.getenv("DW_USUARIO"),
#     password=os.getenv("DW_SENHA"),
#     host=os.getenv("DW_HOST"),
#     port=int(os.getenv("DW_PORTA")),
#     database=os.getenv("DW_BANCO")
# )

# engine_dw = create_engine(url_dw)
