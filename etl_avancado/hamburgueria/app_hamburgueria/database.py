import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "hamburgueria.db"

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS produtos (
            id_produto INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            categoria TEXT NOT NULL,
            preco REAL NOT NULL CHECK (preco >= 0),
            ativo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            origem_pedido TEXT NOT NULL CHECK (origem_pedido IN ('Caixa', 'Garçom')),
            tipo_atendimento TEXT NOT NULL CHECK (tipo_atendimento IN ('Balcão', 'Mesa', 'Retirada')),
            mesa TEXT,
            status TEXT NOT NULL DEFAULT 'Aberto',
            observacao TEXT,
            valor_total REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS itens_pedido (
            id_item INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido INTEGER NOT NULL,
            id_produto INTEGER NOT NULL,
            quantidade INTEGER NOT NULL CHECK (quantidade > 0),
            preco_unitario REAL NOT NULL CHECK (preco_unitario >= 0),
            subtotal REAL NOT NULL CHECK (subtotal >= 0),
            FOREIGN KEY (id_pedido) REFERENCES pedidos(id_pedido),
            FOREIGN KEY (id_produto) REFERENCES produtos(id_produto)
        );
        """)
        count = conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
        if count == 0:
            seed = [
                ("Smash Burger", "Hambúrguer", 22.90),
                ("Cheeseburger", "Hambúrguer", 26.90),
                ("Bacon Burger", "Hambúrguer", 31.90),
                ("Burger Duplo", "Hambúrguer", 34.90),
                ("Batata Frita P", "Acompanhamento", 12.00),
                ("Batata Frita G", "Acompanhamento", 19.00),
                ("Onion Rings", "Acompanhamento", 16.00),
                ("Refrigerante Lata", "Bebida", 6.00),
                ("Suco Natural", "Bebida", 9.00),
                ("Milk-shake", "Bebida", 15.00),
                ("Combo Clássico", "Combo", 39.90),
            ]
            conn.executemany(
                "INSERT INTO produtos (nome, categoria, preco) VALUES (?, ?, ?)", seed
            )

def get_products():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id_produto, nome, categoria, preco FROM produtos WHERE ativo = 1 ORDER BY categoria, nome"
        ).fetchall()
        return [dict(r) for r in rows]

def create_order(origem, atendimento, mesa, observacao, items):
    timestamp = now_iso()
    with get_connection() as conn:
        total = 0.0
        product_prices = {}
        for product_id, qty in items.items():
            row = conn.execute(
                "SELECT preco FROM produtos WHERE id_produto = ? AND ativo = 1",
                (product_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Produto {product_id} não encontrado.")
            product_prices[product_id] = float(row["preco"])
            total += float(row["preco"]) * qty

        cur = conn.execute("""
            INSERT INTO pedidos
            (origem_pedido, tipo_atendimento, mesa, status, observacao, valor_total, created_at, updated_at)
            VALUES (?, ?, ?, 'Aberto', ?, ?, ?, ?)
        """, (origem, atendimento, mesa, observacao, total, timestamp, timestamp))
        order_id = cur.lastrowid

        for product_id, qty in items.items():
            price = product_prices[product_id]
            conn.execute("""
                INSERT INTO itens_pedido
                (id_pedido, id_produto, quantidade, preco_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, product_id, qty, price, price * qty))
        return order_id

def get_orders(limit=None):
    sql = """
        SELECT id_pedido, origem_pedido, tipo_atendimento, mesa, status,
               valor_total, created_at, updated_at
        FROM pedidos
        ORDER BY id_pedido DESC
    """
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    else:
        params = ()
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def update_order_status(order_id, status):
    with get_connection() as conn:
        conn.execute(
            "UPDATE pedidos SET status = ?, updated_at = ? WHERE id_pedido = ?",
            (status, now_iso(), order_id),
        )

def get_order_items(order_id):
    """Retorna os itens com IDs para permitir edição do pedido."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT i.id_produto, p.nome AS produto, i.quantidade,
                   i.preco_unitario, i.subtotal
            FROM itens_pedido i
            JOIN produtos p ON p.id_produto = i.id_produto
            WHERE i.id_pedido = ?
            ORDER BY i.id_item
        """, (order_id,)).fetchall()
        return [dict(r) for r in rows]

def update_order_items(order_id, items):
    """Substitui os itens do pedido e atualiza total/updated_at atomicamente.

    items: dict {id_produto: quantidade}. Mantém o preço histórico dos produtos
    que já estavam no pedido; para novos produtos usa o preço atual do cardápio.
    """
    if not items:
        raise ValueError("O pedido precisa ter pelo menos um item.")

    timestamp = now_iso()
    with get_connection() as conn:
        order = conn.execute(
            "SELECT status FROM pedidos WHERE id_pedido = ?", (order_id,)
        ).fetchone()
        if order is None:
            raise ValueError("Pedido não encontrado.")
        if order["status"] in ("Entregue", "Cancelado"):
            raise ValueError("Pedidos entregues ou cancelados não podem ser editados.")

        old_prices = {
            int(row["id_produto"]): float(row["preco_unitario"])
            for row in conn.execute(
                "SELECT id_produto, preco_unitario FROM itens_pedido WHERE id_pedido = ?",
                (order_id,),
            ).fetchall()
        }

        new_rows = []
        total = 0.0
        for product_id, quantity in items.items():
            product_id, quantity = int(product_id), int(quantity)
            if quantity < 1:
                raise ValueError("A quantidade deve ser maior que zero.")
            if product_id in old_prices:
                price = old_prices[product_id]
            else:
                product = conn.execute(
                    "SELECT preco FROM produtos WHERE id_produto = ? AND ativo = 1",
                    (product_id,),
                ).fetchone()
                if product is None:
                    raise ValueError(f"Produto {product_id} não encontrado ou inativo.")
                price = float(product["preco"])
            subtotal = price * quantity
            total += subtotal
            new_rows.append((order_id, product_id, quantity, price, subtotal))

        conn.execute("DELETE FROM itens_pedido WHERE id_pedido = ?", (order_id,))
        conn.executemany("""
            INSERT INTO itens_pedido
            (id_pedido, id_produto, quantidade, preco_unitario, subtotal)
            VALUES (?, ?, ?, ?, ?)
        """, new_rows)
        conn.execute("""
            UPDATE pedidos
            SET valor_total = ?, updated_at = ?
            WHERE id_pedido = ?
        """, (total, timestamp, order_id))


def get_order_details(order_id):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.nome AS produto, i.quantidade, i.preco_unitario, i.subtotal
            FROM itens_pedido i
            JOIN produtos p ON p.id_produto = i.id_produto
            WHERE i.id_pedido = ?
            ORDER BY i.id_item
        """, (order_id,)).fetchall()
        return [dict(r) for r in rows]

def get_dashboard_metrics():
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0]
        revenue = conn.execute(
            "SELECT COALESCE(SUM(valor_total), 0) FROM pedidos WHERE status <> 'Cancelado'"
        ).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM pedidos WHERE status IN ('Aberto', 'Em preparação')"
        ).fetchone()[0]
        return {
            "total_pedidos": int(total),
            "faturamento": float(revenue),
            "em_andamento": int(active),
        }
