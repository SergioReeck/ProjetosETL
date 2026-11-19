""" Pipeline ETL - Fluxo de execução """

from utils import importar_modulo

setup_dw = importar_modulo("00_setup_dw.py", "setup_dw")
extract = importar_modulo("01_extract.py", "extract")
transform = importar_modulo("02_transform.py", "transform")
load = importar_modulo("03_load.py", "load")

configurar_dw = setup_dw.configurar_dw()
extracao_bd = extract.extracao_bd_loja_brasil()
extracao_ibge = extract.extracao_ibge()
transformacao = transform.transformacao_silver()
carga = load.processar_gold()


def main():
    # Garantindo existencia das camadas
    configurar_dw

    # Extrair dados (E)
    extracao_bd
    extracao_ibge

    # Transformar dados (T)
    transformacao

    # Carregar dados (L)
    carga

    print("Pipeline ETL concluído.")

if __name__ == "__main__":
    main()
    