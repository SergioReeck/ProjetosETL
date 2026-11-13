"""
Registro dos projetos. Rodar a partir da pasta monitor/:  python tarefas.py
Painel: http://localhost:8000

Estrutura esperada:
  repo/
    monitor/    monitor.py, tarefas.py
    projetos/   etl_vendas/src/etl.py, etl_compras/src/etl.py, ...

Cada projeto roda `python src/etl.py` com a pasta do projeto como diretório de trabalho (usa projetos/<nome>/.venv se existir).
Projetos que existem na pasta mas não estão em AGENDA aparecem no painel só com execução manual.
"""
import os

from monitor import projeto, servir

PROJETOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "projetos")

# every = segundos entre execuções | retries = novas tentativas | timeout = segundos máx. por execução
AGENDA = {
    "etl_vendas":  dict(every=3600, retries=2, timeout=1800),
    "etl_compras": dict(every=7200, timeout=1800),
    "etl_exemplo": dict(nome="etl_exemplo teste", every=60, retries=2, timeout=1800),
}

for nome in sorted(os.listdir(PROJETOS)):
    pasta = os.path.join(PROJETOS, nome)
    if os.path.isfile(os.path.join(pasta, "src", "etl.py")):
        projeto(pasta, **AGENDA.get(nome, {}))

if __name__ == "__main__":
    servir(porta=8000)
