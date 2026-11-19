# Hamburgueria Central — Sistema de pedidos

Aplicação para simular um pequeno sistema operacional de hamburgueria.
Os pedidos são registrados por caixa ou garçom e persistidos em SQLite.

## Funcionalidades
- Registro de pedidos do caixa e dos garçons
- Atendimento no balcão, mesa ou retirada
- Seleção de vários produtos e quantidades
- Cálculo automático do total
- Acompanhamento e atualização do status
- Edição de itens e quantidades em pedidos ainda não entregues/cancelados
- Indicadores simples e histórico de pedidos

## Tecnologias
- Python
- Streamlit
- SQLite
- Pandas

## Requisitos
Python 3.10 ou superior.

## Como executar

1. Extraia o ZIP.
2. Abra a pasta do projeto no VS Code.
3. Crie e ative um ambiente virtual (recomendado):

### Windows
```bash
python -m venv .venv
.venv\\Scripts\\activate
```

### Linux / macOS
```bash
python -m venv .venv
source .venv/bin/activate
```

OBS: caso tenha problema de permissão ao ativar o .venv: ```Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser``` 

4. Instale as dependências:

```bash
pip install -r requirements.txt
```

5. Execute a aplicação:

```bash
streamlit run app.py
```

O navegador abrirá a aplicação. Na primeira execução, o banco será criado automaticamente em `data/hamburgueria.db`, com um cardápio inicial.

## Estrutura do banco SQLite

### produtos
Cadastro dos produtos disponíveis no cardápio.

### pedidos
Um registro por pedido. Campos importantes:
- `id_pedido`: chave primária
- `created_at`: data/hora de criação
- `updated_at`: data/hora da última atualização
- `status`: situação atual do pedido
- `valor_total`: total do pedido

### itens_pedido
Produtos e quantidades pertencentes a cada pedido.

## Consultas SQL para explorar no SQLite

```sql
SELECT * FROM pedidos ORDER BY id_pedido;
```

```sql
SELECT
    p.id_pedido,
    p.origem_pedido,
    p.status,
    p.created_at,
    p.updated_at,
    i.id_produto,
    pr.nome AS produto,
    i.quantidade,
    i.preco_unitario,
    i.subtotal
FROM pedidos p
JOIN itens_pedido i ON i.id_pedido = p.id_pedido
JOIN produtos pr ON pr.id_produto = i.id_produto
ORDER BY p.id_pedido, i.id_item;
```

## Preparação para a próxima etapa: ETL

A aplicação separa o banco operacional do futuro banco analítico.
A edição de um pedido substitui seus itens dentro de uma transação, recalcula `valor_total` e atualiza `updated_at`, preservando `created_at` e `id_pedido`. Pedidos entregues ou cancelados ficam bloqueados para edição.

Na próxima etapa, o Python poderá extrair `pedidos`, `itens_pedido` e `produtos`
do SQLite e carregar os dados no PostgreSQL.

- Carga full: extrair todos os registros e substituir o conjunto no destino.
- Append: buscar pedidos com `created_at` posterior ao último ponto de controle e inserir somente novos IDs.
- Update: buscar registros alterados por `updated_at` e atualizar os IDs existentes.
- Upsert: inserir IDs novos e atualizar IDs já existentes.

**Atenção:** `created_at` identifica criação; `updated_at` identifica alteração.
