from utils import extrair_dados, gravar_bronze, importar_modulo

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

    tabelas = [
        ("vendas", sql_vendas, "loja_brasil_vendas"),
        ("clientes", sql_clientes, "loja_brasil_clientes"),
        ("produtos", sql_produtos, "loja_brasil_produtos"),
        ("vendedores", sql_vendedores, "loja_brasil_vendedores"),
    ]

    for descricao, query_sql, nome_tabela in tabelas:
        print(f"Extração da tabela de {descricao}")
        df = extrair_dados(query_sql, engine_erp)
        gravar_bronze(df, nome_tabela, engine_dw)

    print("Extração do banco de dados LOJA BRASIL concluída.")
    print("Dados gravados na camada BRONZE.")
