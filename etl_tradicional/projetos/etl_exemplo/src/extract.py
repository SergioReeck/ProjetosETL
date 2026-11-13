"""Extração: leitura dos dados de origem."""

import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ARQUIVO_ORIGEM = ROOT_DIR / "data" / "raw" / "vendas.csv"


def extrair_dados():
    with open(ARQUIVO_ORIGEM, mode="r", encoding="utf-8", newline="") as arquivo:
        dados = list(csv.DictReader(arquivo))

    print(f"{len(dados)} registros extraídos.")
    return dados
