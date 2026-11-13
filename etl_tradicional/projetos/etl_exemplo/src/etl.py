"""Pipeline ETL - Fluxo de execução."""

from extract import extrair_dados
from transform import transformar_dados
from load import carregar_dados


def main():

    print("Iniciando pipeline ETL...")

    # E - Extração
    dados = extrair_dados()

    # T - Transformação
    dados_tratados = transformar_dados(dados)

    # L - Carga
    carregar_dados(dados_tratados)

    print("Pipeline ETL concluído.")


if __name__ == "__main__":
    main()