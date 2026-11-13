"""Transformação: limpeza e enriquecimento dos dados."""


def transformar_dados(dados):
    dados_tratados = []

    for registro in dados:
        produto = registro["produto"].strip()

        # Remove registros sem produto ou com quantidade inválida.
        if not produto or int(registro["quantidade"]) <= 0:
            continue

        quantidade = int(registro["quantidade"])
        preco_unitario = float(registro["preco_unitario"])

        dados_tratados.append({
            "id_venda": int(registro["id_venda"]),
            "produto": produto,
            "quantidade": quantidade,
            "preco_unitario": preco_unitario,
            "valor_total": round(quantidade * preco_unitario, 2),
        })

    print(f"{len(dados_tratados)} registros após a transformação.")
    return dados_tratados
