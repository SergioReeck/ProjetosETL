import pandas as pd
from config import engine_erp, engine_dw

# ---------- SQL Query ---------- # 

sql_vendas = """
SELECT
    p.id_pedido,
    p.data_pedido,
    p.status AS status_pedido,
    p.id_cliente,
    i.id_produto,
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

    print("Extração da tabela de vendas")
    df_vendas = pd.read_sql(sql_vendas, engine_erp)

    df_vendas.to_sql(
        "loja_brasil_vendas",
        engine_dw,
        schema="bronze",
        if_exists="replace",
        index=False
    )


    print("Extração da tabela de clientes")
    df_clientes = pd.read_sql(sql_clientes, engine_erp)

    df_clientes.to_sql(
        "loja_brasil_clientes",
        engine_dw,
        schema="bronze",
        if_exists="replace",
        index=False
    )


    print("Extração da tabela de produtos")
    df_produtos = pd.read_sql(sql_produtos, engine_erp)

    df_produtos.to_sql(
        "loja_brasil_produtos",
        engine_dw,
        schema="bronze",
        if_exists="replace",
        index=False
    )


    print("Extração da tabela de vendedores")
    df_vendedores = pd.read_sql(sql_vendedores, engine_erp)

    df_vendedores.to_sql(
        "loja_brasil_vendedores",
        engine_dw,
        schema="bronze",
        if_exists="replace",
        index=False
    )


    del df_vendas, df_clientes, df_produtos, df_vendedores

    print("Extração do banco de dados LOJA BRASIL concluída.")
    print("Dados gravados na camada BRONZE.")
