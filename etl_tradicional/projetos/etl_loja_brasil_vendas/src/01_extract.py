import pandas as pd
import requests
from utils import gravar_dados, importar_modulo, ler_dados

config = importar_modulo("00_config.py", "config")

engine_erp = config.engine_erp
engine_dw = config.engine_dw

# ---------- SQL Query ---------- # 

sql_vendas = """
SELECT
    p.id_pedido,
    p.data_pedido,
    p.status AS status_pedido,
    p.id_cliente,
    i.id_produto,
    p.id_funcionario AS id_vendedor,
    i.quantidade,
    i.preco_unitario,
    i.desconto
FROM vendas.pedidos p
INNER JOIN vendas.itens_pedido i 
    ON i.id_pedido = p.id_pedido
"""

sql_clientes = """
SELECT
	id_cliente,
	cidade,
	estado 
FROM cadastro.clientes;
"""

sql_produtos = """
SELECT
	p.id_produto,
	p.nome AS produto,
	c.nome AS categoria
FROM cadastro.produtos p
LEFT JOIN cadastro.categorias c
	ON p.id_categoria = c.id_categoria 
LEFT JOIN cadastro.marcas m
	ON p.id_marca = m.id_marca;
"""

sql_vendedores = """
SELECT DISTINCT 
	f.id_funcionario AS id_vendedor,
	f.nome,
	c.nome AS cargo
FROM rh.funcionarios f
JOIN vendas.pedidos p
	ON f.id_funcionario = p.id_funcionario 
LEFT JOIN rh.cargos c
	ON f.id_cargo = c.id_cargo;
"""

# ---------- SQL Query ---------- # 


def extracao_bd_loja_brasil():
    print("Extraindo dados do banco de dados LOJA BRASIL...")

    extracoes = {
        "vendas": (sql_vendas, "loja_brasil_vendas"),
        "clientes": (sql_clientes, "loja_brasil_clientes"),
        "produtos": (sql_produtos, "loja_brasil_produtos"),
        "vendedores": (sql_vendedores, "loja_brasil_vendedores"),
    }

    camada = "bronze"

    for nome, (query_sql, nome_tabela) in extracoes.items():
        print(f"Extração da tabela bronze.{nome}")
        df = ler_dados(query_sql, engine_erp)
        gravar_dados(df, nome_tabela, engine_dw, camada)

    print("Extração do banco de dados LOJA BRASIL concluída.")
    print("Dados gravados na camada BRONZE.")


def extracao_ibge():
    print("Extraindo dados do IBGE...")
    url_ibge = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/42/municipios"

    response = requests.get(url_ibge, timeout=30)
    response.raise_for_status()

    dados_ibge = response.json()

    df_ibge = pd.DataFrame([
        {
            "id_ibge": municipio["id"],
            "cidade": municipio["nome"],
            "estado": municipio["microrregiao"]["mesorregiao"]["UF"]["sigla"],
            "regiao": municipio["microrregiao"]["mesorregiao"]["UF"]["regiao"]["nome"],
            "mesorregiao": municipio["microrregiao"]["mesorregiao"]["nome"],
            "microrregiao": municipio["microrregiao"]["nome"],
            "regiao_imediata": municipio["regiao-imediata"]["nome"],
            "regiao_intermediaria": municipio["regiao-imediata"]["regiao-intermediaria"]["nome"]
        }
        for municipio in dados_ibge
    ])

    gravar_dados(df_ibge, "api_ibge_municipios", engine_dw, "bronze")

    print("Extração do IBGE concluída.")
    print("Dados gravados na camada BRONZE.")
