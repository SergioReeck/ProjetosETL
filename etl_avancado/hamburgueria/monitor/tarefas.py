"""
Registro dos projetos.
Rodar: python tarefas.py

Painel: http://localhost:8000
"""

import os

from monitor import projeto, servir
from datetime import datetime
from croniter import croniter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASTA_ETL = os.path.join(RAIZ, "etl_hamburgueria")


projeto(
    PASTA_ETL,
    nome="ETL Hamburgueria",
    modulo="src.etl",
    modos=("full", "incremental"),
    modo_padrao="incremental",
    tipo_agendamento="cron",
    cron="*/1 * * * *",
)


if __name__ == "__main__":
    servir(porta=8000)
    