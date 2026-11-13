"""Carga: grava os dados transformados."""

import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ARQUIVO_DESTINO = ROOT_DIR / "data" / "processed" / "vendas_tratadas.csv"


def carregar_dados(dados):
    ARQUIVO_DESTINO.parent.mkdir(parents=True, exist_ok=True)

    if not dados:
        print("Nenhum dado para carregar.")
        return

    with open(ARQUIVO_DESTINO, mode="w", encoding="utf-8", newline="") as arquivo:
        campos = dados[0].keys()
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(dados)

    print(f"Dados carregados em: {ARQUIVO_DESTINO}")
