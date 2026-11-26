import argparse

from src.raw_to_bronze import executar as raw_to_bronze
from src.bronze_to_silver import executar as bronze_to_silver
from src.silver_to_gold import executar as silver_to_gold


def executar_etl(modo):
    """
    Executa o fluxo completo de ETL.

    modo: "full" ou "incremental"
    """
    if modo not in ("full", "incremental"):
        raise ValueError("O modo deve ser 'full' ou 'incremental'.")

    print(f"\\nIniciando ETL — carga {modo.upper()}\\n")

    raw_to_bronze(modo)
    bronze_to_silver(modo)
    silver_to_gold(modo)

    print("\\nETL finalizada!\\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Executa o ETL da hamburgueria.")
    parser.add_argument(
        "modo",
        nargs="?",
        choices=("full", "incremental"),
        default="incremental",
        help="tipo de carga (padrão: incremental)",
    )
    executar_etl(modo=parser.parse_args().modo)
    