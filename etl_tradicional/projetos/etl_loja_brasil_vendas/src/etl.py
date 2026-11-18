""" Pipeline ETL - Fluxo de execução """

from utils import importar_modulo

setup_dw = importar_modulo("00_setup_dw.py", "setup_dw")
extract = importar_modulo("01_extract.py", "extract")

configurar_dw = setup_dw.configurar_dw()
extracao = extract.extracao_bd_loja_brasil()

# from setup_dw import configurar_dw
# from extract_erp import extrair_erp
# from silver import processar_silver
# from gold import processar_gold


def main():
    # Garantindo existencia das camadas
    configurar_dw

    # Extrair dados (E)
    extracao

    # Transformar dados (T)
    # processar_silver()

    # Carregar dados (L)
    # processar_gold()

    print("Pipeline ETL concluído.")


if __name__ == "__main__":
    main()
    