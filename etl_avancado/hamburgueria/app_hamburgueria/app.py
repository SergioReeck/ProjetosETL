import streamlit as st
import pandas as pd
from database import (
    init_db, get_products, create_order, get_orders, update_order_status,
    get_order_details, get_order_items, update_order_items, get_dashboard_metrics
)

st.set_page_config(page_title="Hamburgueria | Pedidos", page_icon="🍔", layout="wide")
init_db()

st.title("🍔 Hamburgueria Central")
st.caption("Sistema demonstrativo de pedidos — Caixa e garçons")

menu = st.sidebar.radio(
    "Navegação",
    ["Painel", "Novo pedido", "Pedidos", "Cardápio"],
)
st.sidebar.divider()
st.sidebar.caption("Banco operacional: SQLite")
st.sidebar.caption("Aplicação didática para o projeto de ETL")

if menu == "Painel":
    st.subheader("Visão geral")
    metrics = get_dashboard_metrics()
    c1, c2, c3 = st.columns(3)
    c1.metric("Pedidos registrados", metrics["total_pedidos"])
    c2.metric("Faturamento (não cancelados)", f'R$ {metrics["faturamento"]:,.2f}'.replace(",", "X").replace(".", ",").replace("X", "."))
    c3.metric("Pedidos em aberto/preparação", metrics["em_andamento"])

    st.info("Registre pedidos no caixa ou pelos garçons. Depois, altere seus status para gerar atualizações no banco SQLite.")
    st.markdown("#### Últimos pedidos")
    orders = get_orders(limit=10)
    if orders:
        df = pd.DataFrame(orders)
        df["valor_total"] = df["valor_total"].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.write("Ainda não existem pedidos. Comece em **Novo pedido**.")

elif menu == "Novo pedido":
    st.subheader("Registrar pedido")
    products = get_products()
    product_map = {p["nome"]: p for p in products}

    with st.form("form_pedido", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        origem = col1.selectbox("Origem do pedido", ["Caixa", "Garçom"])
        atendimento = col2.selectbox("Tipo de atendimento", ["Balcão", "Mesa", "Retirada"])
        mesa = col3.text_input("Mesa (se aplicável)", placeholder="Ex.: 04")

        st.markdown("#### Itens do pedido")
        selected = st.multiselect(
            "Selecione os produtos",
            options=list(product_map.keys()),
        )
        quantities = {}
        total = 0.0
        if selected:
            cols = st.columns(min(3, len(selected)))
            for i, name in enumerate(selected):
                p = product_map[name]
                with cols[i % len(cols)]:
                    qty = st.number_input(
                        f"Quantidade — {name} (R$ {p['preco']:.2f})",
                        min_value=1, max_value=30, value=1, step=1, key=f"qty_{p['id_produto']}"
                    )
                    quantities[p["id_produto"]] = int(qty)
                    total += p["preco"] * qty
        st.markdown(f"### Total: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        observacao = st.text_input("Observações", placeholder="Ex.: sem cebola, ponto da carne...")
        submitted = st.form_submit_button("Confirmar pedido", type="primary", use_container_width=True)

        if submitted:
            if not selected:
                st.error("Selecione pelo menos um produto.")
            elif origem == "Garçom" and atendimento == "Mesa" and not mesa.strip():
                st.error("Informe a mesa para pedidos de garçom no salão.")
            else:
                order_id = create_order(
                    origem=origem,
                    atendimento=atendimento,
                    mesa=mesa.strip() or None,
                    observacao=observacao.strip() or None,
                    items=quantities,
                )
                st.success(f"Pedido #{order_id} registrado com sucesso!")

elif menu == "Pedidos":
    st.subheader("Acompanhamento de pedidos")
    orders = get_orders()
    if not orders:
        st.info("Nenhum pedido registrado ainda.")
    else:
        df = pd.DataFrame(orders)
        statuses = ["Aberto", "Em preparação", "Pronto", "Entregue", "Cancelado"]
        for _, row in df.iterrows():
            with st.expander(
                f"Pedido #{row['id_pedido']} | {row['origem_pedido']} | {row['status']} | R$ {row['valor_total']:.2f}"
            ):
                a, b, c = st.columns([2, 2, 3])
                a.write(f"**Atendimento:** {row['tipo_atendimento']}")
                b.write(f"**Mesa:** {row['mesa'] or '—'}")
                c.write(f"**Criado em:** {row['created_at']}")
                order_id = int(row["id_pedido"])
                details = get_order_details(order_id)
                if details:
                    st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True)

                current = row["status"]
                new_status = st.selectbox(
                    "Atualizar status",
                    statuses,
                    index=statuses.index(current),
                    key=f"status_{order_id}",
                )
                if st.button("Salvar status", key=f"save_{order_id}"):
                    if new_status != current:
                        update_order_status(order_id, new_status)
                        st.success("Status atualizado. O campo updated_at também foi alterado.")
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração realizada.")

                if current not in ("Entregue", "Cancelado"):
                    st.markdown("#### Editar itens e quantidades")
                    current_items = get_order_items(order_id)
                    products = get_products()
                    product_map = {p["nome"]: p for p in products}
                    id_to_name = {p["id_produto"]: p["nome"] for p in products}
                    existing_names = [
                        id_to_name[item["id_produto"]]
                        for item in current_items
                        if item["id_produto"] in id_to_name
                    ]
                    with st.form(f"edit_order_{order_id}"):
                        selected_names = st.multiselect(
                            "Produtos do pedido (remova da seleção para excluir)",
                            options=list(product_map.keys()),
                            default=existing_names,
                            key=f"edit_products_{order_id}",
                        )
                        edited_items = {}
                        edit_cols = st.columns(min(3, max(1, len(selected_names))))
                        old_qty = {item["id_produto"]: item["quantidade"] for item in current_items}
                        for i, name in enumerate(selected_names):
                            product = product_map[name]
                            with edit_cols[i % len(edit_cols)]:
                                qty = st.number_input(
                                    f"{name} — R$ {product['preco']:.2f}",
                                    min_value=1, max_value=30,
                                    value=int(old_qty.get(product["id_produto"], 1)),
                                    step=1,
                                    key=f"edit_qty_{order_id}_{product['id_produto']}"
                                )
                            edited_items[product["id_produto"]] = int(qty)
                        estimated_total = sum(
                            product_map[name]["preco"] * edited_items[product_map[name]["id_produto"]]
                            for name in selected_names
                        )
                        st.write(f"**Total estimado com preços atuais do cardápio: R$ {estimated_total:.2f}**")
                        save_items = st.form_submit_button("Salvar alterações do pedido")
                        if save_items:
                            if not edited_items:
                                st.error("O pedido precisa ter pelo menos um produto.")
                            else:
                                try:
                                    update_order_items(order_id, edited_items)
                                    st.success("Itens atualizados e total recalculado. O updated_at foi atualizado.")
                                    st.rerun()
                                except ValueError as exc:
                                    st.error(str(exc))
                else:
                    st.caption("Pedidos entregues ou cancelados não podem mais ter seus itens editados.")

elif menu == "Cardápio":
    st.subheader("Cardápio cadastrado")
    products = get_products()
    df = pd.DataFrame(products)
    df["preco"] = df["preco"].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.dataframe(df[["id_produto", "nome", "categoria", "preco"]], use_container_width=True, hide_index=True)
