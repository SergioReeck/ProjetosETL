# Projeto ETL Simples

Exemplo didático de um pipeline ETL em Python, organizado em módulos.

## Estrutura

```text
projeto_etl_simples/
├── data/
│   ├── raw/
│   │   └── vendas.csv
│   └── processed/
├── src/
│   ├── __init__.py
│   ├── extract.py
│   ├── transform.py
│   ├── load.py
│   └── etl.py
└── README.md
```

## Responsabilidade dos arquivos

- `extract.py`: lê os dados de origem (`data/raw/vendas.csv`).
- `transform.py`: remove registros inválidos e calcula o valor total da venda.
- `load.py`: grava os dados tratados em `data/processed/vendas_tratadas.csv`.
- `etl.py`: coordena a execução das etapas de extração, transformação e carga.

## Como executar

Execute o comando a partir da pasta raiz do projeto:

```bash
python -m src.etl
```

O projeto utiliza apenas bibliotecas nativas do Python, sem necessidade de instalar dependências externas.


cd projetos/etl_exemplo
python src/etl.py