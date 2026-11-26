"""
monitor.py - mini-orquestrador de tarefas Python.

Recursos:
- Registro de tarefas Python por função ou por projeto.
- Agendamento por cron, intervalo em segundos ou execução manual.
- Seleção de modo (ex.: full/incremental) pela interface.
- Execução agendada usando o modo_agendado (incremental por padrão).
- Histórico de execuções em SQLite.
- Logs por execução e atualização automática do painel.
- Retries, timeout e proteção contra execuções simultâneas.

Dependência para agendamento cron:
    pip install croniter

Uso:
    from monitor import projeto, servir
    projeto(..., tipo_agendamento="cron", cron="*/5 * * * *")
    servir(porta=8000)
"""

import io
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

try:
    from croniter import croniter
except ImportError:
    croniter = None


AQUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(AQUI, "monitor.db")
RETENCAO_DIAS = 30
HISTORICO = 30

TAREFAS = {}
_lock = threading.RLock()
_local = threading.local()


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

_con = sqlite3.connect(DB, check_same_thread=False)
_con.row_factory = sqlite3.Row

with _lock:
    _con.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY,
            tarefa TEXT,
            status TEXT,
            inicio REAL,
            fim REAL,
            log TEXT
        )
        """
    )
    _con.execute("CREATE INDEX IF NOT EXISTS ix_runs ON runs(tarefa, id)")
    _con.execute(
        "UPDATE runs SET status='interrompida', fim=inicio "
        "WHERE status='rodando'"
    )
    _con.commit()


def sql(query, *args):
    """Executa uma instrução SQL usando a conexão compartilhada."""
    with _lock:
        cur = _con.execute(query, args)
        _con.commit()
        return cur.lastrowid, cur.fetchall() if cur.description else []


# ---------------------------------------------------------------------------
# Captura de saída das tarefas
# ---------------------------------------------------------------------------

class _Saida:
    """Replica stdout no terminal e no log da execução da thread atual."""

    def __init__(self, original):
        self.original = original

    def write(self, texto):
        self.original.write(texto)
        buf = getattr(_local, "buf", None)

        if buf is not None:
            buf.write(texto)
            agora = time.time()

            if agora - getattr(_local, "salvo", 0) >= 1:
                _local.salvo = agora
                sql(
                    "UPDATE runs SET log=? WHERE id=?",
                    buf.getvalue(),
                    _local.rid,
                )

        return len(texto)

    def flush(self):
        self.original.flush()

    def __getattr__(self, nome):
        return getattr(self.original, nome)


if not isinstance(sys.stdout, _Saida):
    sys.stdout = _Saida(sys.stdout)


# ---------------------------------------------------------------------------
# Agendamento
# ---------------------------------------------------------------------------

TIPOS_AGENDAMENTO = ("cron", "intervalo", "manual")


def proxima_execucao(tarefa, referencia=None):
    """
    Calcula o próximo horário de execução.

    Cron usa o horário local da máquina onde o monitor está executando.
    Intervalo é calculado em segundos a partir da referência.
    Manual não possui próxima execução.
    """
    tipo = tarefa["tipo_agendamento"]

    if tipo == "manual":
        return None

    agora = referencia if referencia is not None else time.time()

    if tipo == "intervalo":
        return agora + tarefa["intervalo"]

    if tipo == "cron":
        if croniter is None:
            raise RuntimeError(
                "Para usar agendamento cron, instale a dependência: "
                "pip install croniter"
            )

        base = datetime.fromtimestamp(agora)
        proxima = croniter(tarefa["cron"], base).get_next(datetime)
        return proxima.timestamp()

    raise ValueError(f"Tipo de agendamento desconhecido: {tipo}")


def _validar_agendamento(tipo_agendamento, cron, intervalo):
    if tipo_agendamento not in TIPOS_AGENDAMENTO:
        raise ValueError(
            "tipo_agendamento deve ser 'cron', 'intervalo' ou 'manual'."
        )

    if tipo_agendamento == "cron":
        if croniter is None:
            raise RuntimeError(
                "Dependência croniter não instalada. Execute: pip install croniter"
            )
        if not cron or not croniter.is_valid(cron):
            raise ValueError(f"Expressão cron inválida: {cron!r}")

    elif tipo_agendamento == "intervalo":
        if isinstance(intervalo, bool) or not isinstance(intervalo, (int, float)):
            raise ValueError("intervalo deve ser um número de segundos.")
        if intervalo <= 0:
            raise ValueError("intervalo deve ser maior que zero.")


# ---------------------------------------------------------------------------
# Registro de tarefas
# ---------------------------------------------------------------------------

def tarefa(every=None, retries=0, nome=None):
    """
    Registra uma função Python para execução manual ou periódica.

    Compatibilidade: every=segundos continua aceito para tarefas simples.
    """
    def deco(fn):
        intervalo = every
        tipo = "intervalo" if intervalo is not None else "manual"

        registro = {
            "fn": fn,
            "every": intervalo,
            "retries": retries,
            "next": None,
            "running": False,
            "modos": None,
            "modo_padrao": None,
            "modo_agendado": None,
            "tipo_agendamento": tipo,
            "cron": None,
            "intervalo": intervalo,
        }
        registro["next"] = proxima_execucao(registro)
        TAREFAS[nome or fn.__name__] = registro
        return fn

    return deco


def _python_do_projeto(pasta):
    """Usa o ambiente virtual do projeto, se existir."""
    for venv in (".venv", "venv"):
        for sub in ("bin/python", "Scripts/python.exe"):
            caminho = os.path.join(pasta, venv, sub)
            if os.path.exists(caminho):
                return caminho
    return sys.executable


class ErroProjeto(Exception):
    """Erro de execução de um projeto externo."""


def projeto(
    pasta,
    every=None,
    retries=0,
    timeout=None,
    nome=None,
    script="src/etl.py",
    modulo=None,
    args=(),
    modos=None,
    modo_padrao=None,
    modo_agendado="incremental",
    tipo_agendamento="manual",
    cron=None,
    intervalo=None,
):
    """
    Registra um projeto Python.

    tipo_agendamento:
        "cron"      -> exige cron="*/5 * * * *"
        "intervalo" -> exige intervalo=5 (segundos)
        "manual"    -> sem agendamento automático

    modos:
        Lista de argumentos aceitos pelo projeto, por exemplo
        ("full", "incremental").

    modo_padrao:
        Modo usado quando a execução manual não informa um modo.

    modo_agendado:
        Modo utilizado pelo agendador. Para ETL, normalmente "incremental".
    """
    pasta = os.path.abspath(pasta)
    nome = nome or os.path.basename(pasta)

    # Compatibilidade com a antiga configuração every=segundos.
    if every is not None:
        if tipo_agendamento != "manual" or intervalo is not None:
            raise ValueError(
                "Use tipo_agendamento='intervalo' e intervalo=...; "
                "não combine com every."
            )
        tipo_agendamento = "intervalo"
        intervalo = every

    _validar_agendamento(tipo_agendamento, cron, intervalo)

    if modos:
        modos = tuple(modos)

        if modo_padrao is not None and modo_padrao not in modos:
            raise ValueError("modo_padrao precisa estar em modos.")

        if modo_agendado is not None and modo_agendado not in modos:
            raise ValueError("modo_agendado precisa estar em modos.")

    def rodar(modo=None):
        comando = [_python_do_projeto(pasta), "-u"]

        if modulo:
            comando.extend(["-m", modulo])
        else:
            comando.append(script)

        comando.extend(args)

        if modos:
            modo_execucao = modo or modo_padrao

            if modo_execucao is None:
                raise ValueError(
                    f"A tarefa {nome!r} exige um modo de execução."
                )

            if modo_execucao not in modos:
                raise ValueError(f"Modo inválido: {modo_execucao}")

            comando.append(modo_execucao)

        print(f"$ {' '.join(comando)}   (em {pasta})")

        processo = subprocess.Popen(
            comando,
            cwd=pasta,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        estourou = []
        timer = None

        if timeout:
            def matar():
                estourou.append(True)
                processo.kill()

            timer = threading.Timer(timeout, matar)
            timer.daemon = True
            timer.start()

        try:
            if processo.stdout:
                for linha in processo.stdout:
                    print(linha, end="")

            codigo = processo.wait()
        finally:
            if timer:
                timer.cancel()

            if processo.poll() is None:
                processo.kill()
                processo.wait()

        if estourou:
            raise ErroProjeto(f"excedeu o timeout de {timeout}s")

        if codigo != 0:
            alvo = f"módulo {modulo}" if modulo else script
            raise ErroProjeto(f"{alvo} terminou com código {codigo}")

    registro = {
        "fn": rodar,
        "every": intervalo if tipo_agendamento == "intervalo" else None,
        "retries": retries,
        "next": None,
        "running": False,
        "modos": modos,
        "modo_padrao": modo_padrao,
        "modo_agendado": modo_agendado if modos else None,
        "tipo_agendamento": tipo_agendamento,
        "cron": cron,
        "intervalo": intervalo if tipo_agendamento == "intervalo" else None,
    }

    registro["next"] = proxima_execucao(registro)
    TAREFAS[nome] = registro


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def executar(nome, modo=None):
    """Dispara uma tarefa em uma thread, sem bloquear o servidor web."""
    with _lock:
        tarefa_registrada = TAREFAS.get(nome)

        if tarefa_registrada is None:
            return False

        if tarefa_registrada["running"]:
            return False

        modos = tarefa_registrada.get("modos")

        if modos:
            modo = modo or tarefa_registrada.get("modo_padrao")

            if modo not in modos:
                return False
        elif modo is not None:
            return False

        tarefa_registrada["running"] = True

    thread = threading.Thread(
        target=_rodar,
        args=(nome, modo),
        daemon=True,
    )
    thread.start()
    return True


def _rodar(nome, modo=None):
    tarefa_registrada = TAREFAS[nome]
    rid, _ = sql(
        "INSERT INTO runs(tarefa,status,inicio,log) VALUES(?,?,?,?)",
        nome,
        "rodando",
        time.time(),
        "",
    )

    _local.buf = io.StringIO()
    _local.rid = rid
    _local.salvo = 0
    status = "falha"

    try:
        total_tentativas = tarefa_registrada["retries"] + 1

        for tentativa in range(total_tentativas):
            try:
                if tentativa:
                    print(
                        f"--- tentativa {tentativa + 1} "
                        f"de {total_tentativas} ---"
                    )

                if tarefa_registrada.get("modos"):
                    tarefa_registrada["fn"](modo)
                else:
                    tarefa_registrada["fn"]()

                status = "sucesso"
                break

            except ErroProjeto as erro:
                print(f"[monitor] {erro}")

            except Exception:
                print(traceback.format_exc())

            if tentativa < total_tentativas - 1:
                time.sleep(min(5 * (tentativa + 1), 30))

    finally:
        log = _local.buf.getvalue()
        _local.buf = None

        sql(
            "UPDATE runs SET status=?, fim=?, log=? WHERE id=?",
            status,
            time.time(),
            log,
            rid,
        )

        with _lock:
            tarefa_registrada["running"] = False


# ---------------------------------------------------------------------------
# Agendador
# ---------------------------------------------------------------------------

def _agendador():
    ultima_limpeza = 0

    while True:
        agora = time.time()

        for nome, tarefa_registrada in list(TAREFAS.items()):
            if tarefa_registrada["tipo_agendamento"] == "manual":
                continue

            proxima = tarefa_registrada.get("next")

            if proxima is not None and agora >= proxima:
                # Calcula a próxima ocorrência antes de disparar a atual.
                # Se a tarefa já estiver rodando, a ocorrência atual é ignorada.
                tarefa_registrada["next"] = proxima_execucao(
                    tarefa_registrada,
                    agora,
                )

                modo = (
                    tarefa_registrada.get("modo_agendado")
                    if tarefa_registrada.get("modos")
                    else None
                )

                iniciou = executar(nome, modo)

                if not iniciou and not tarefa_registrada["running"]:
                    print(
                        f"[monitor] Não foi possível iniciar a tarefa {nome}."
                    )

        if agora - ultima_limpeza > 3600:
            sql(
                "DELETE FROM runs WHERE inicio < ?",
                agora - RETENCAO_DIAS * 86400,
            )
            ultima_limpeza = agora

        time.sleep(0.5)


# ---------------------------------------------------------------------------
# API de status e página
# ---------------------------------------------------------------------------

def _status():
    saida = []

    for nome, tarefa_registrada in TAREFAS.items():
        _, rows = sql(
            """
            SELECT id,status,inicio,fim
            FROM runs
            WHERE tarefa=?
            ORDER BY id DESC
            LIMIT ?
            """,
            nome,
            HISTORICO,
        )

        historico = [
            {
                "id": row["id"],
                "status": row["status"],
                "inicio": row["inicio"],
                "dur": (
                    row["fim"] - row["inicio"]
                    if row["fim"] is not None
                    else None
                ),
            }
            for row in reversed(rows)
        ]

        saida.append(
            {
                "nome": nome,
                "every": tarefa_registrada.get("every"),
                "rodando": tarefa_registrada["running"],
                "proxima": tarefa_registrada.get("next"),
                "historico": historico,
                "modos": tarefa_registrada.get("modos"),
                "modo_padrao": tarefa_registrada.get("modo_padrao"),
                "tipo_agendamento": tarefa_registrada["tipo_agendamento"],
                "cron": tarefa_registrada.get("cron"),
                "intervalo": tarefa_registrada.get("intervalo"),
            }
        )

    return saida


PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de tarefas</title>
<style>
:root {
  --bg:#f6f7f9; --card:#fff; --tx:#1d2330; --mut:#6b7385;
  --bd:#e3e6ec; --ok:#2e9e5b; --err:#d64545; --run:#e0a21b; --int:#9aa1b0;
}
@media(prefers-color-scheme:dark) {
  :root { --bg:#14171d; --card:#1d222b; --tx:#e8eaf0; --mut:#8b93a5; --bd:#2c3340; }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--tx); font:15px/1.45 system-ui,sans-serif; }
main { max-width:1000px; margin:0 auto; padding:20px 16px; }
header { display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; }
h1 { font-size:20px; margin:0; }
.mut { color:var(--mut); font-size:13px; }
.resumo { display:flex; gap:10px; margin:16px 0; flex-wrap:wrap; }
.pill { background:var(--card); border:1px solid var(--bd); border-radius:8px; padding:8px 14px; }
.pill b { font-size:18px; margin-right:6px; }
.card { background:var(--card); border:1px solid var(--bd); border-radius:10px; padding:14px 16px; margin-bottom:10px; }
.topo { display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; }
.nome { font-weight:600; }
.badge { display:inline-block; font-size:11px; padding:2px 8px; border-radius:10px; color:#fff; margin-left:8px; }
.sucesso { background:var(--ok); } .falha { background:var(--err); }
.rodando { background:var(--run); } .interrompida,.nunca { background:var(--int); }
.grade { display:flex; gap:3px; margin-top:10px; flex-wrap:wrap; }
.q { width:16px; height:16px; border-radius:3px; cursor:pointer; border:0; padding:0; }
.q.rodando { animation:p 1s infinite; }
@keyframes p { 50% { opacity:.4; } }
button.run, select {
  background:var(--card); border:1px solid var(--bd); color:var(--tx);
  border-radius:6px; padding:6px 10px; cursor:pointer;
}
button.run:hover:not(:disabled) { border-color:var(--tx); }
button.run:disabled { opacity:.4; cursor:default; }
.acoes { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.linha-info { margin-top:5px; }
dialog { width:min(800px,94vw); background:var(--card); color:var(--tx); border:1px solid var(--bd); border-radius:10px; }
dialog::backdrop { background:#0008; }
pre { background:var(--bg); padding:12px; border-radius:6px; overflow:auto; max-height:55vh; font-size:13px; white-space:pre-wrap; }
</style>
</head>
<body>
<main>
  <header><h1>Monitor de tarefas</h1><span class="mut" id="atual"></span></header>
  <div class="resumo" id="resumo"></div>
  <div id="lista"></div>
  <dialog id="dlg">
    <div class="topo"><b id="dt"></b><button class="run" onclick="dlg.close()">Fechar</button></div>
    <p class="mut" id="dm"></p><pre id="dl"></pre>
  </dialog>
</main>
<script>
const dlg = document.getElementById('dlg');
const esc = s => String(s).replace(/[&<>"']/g, c => ({
  '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
}[c]));
const fmt = t => t ? new Date(t*1000).toLocaleString('pt-BR') : '—';
const dur = s => s==null ? '' : s<60 ? s.toFixed(1)+'s' : Math.floor(s/60)+'min '+Math.round(s%60)+'s';
const cor = {sucesso:'var(--ok)', falha:'var(--err)', rodando:'var(--run)', interrompida:'var(--int)'};

function descricaoAgendamento(t) {
  if (t.tipo_agendamento === 'cron') return 'Cron: ' + esc(t.cron);
  if (t.tipo_agendamento === 'intervalo') return 'Intervalo: ' + esc(t.intervalo) + ' segundos';
  return 'Execução manual';
}

async function carregar() {
  try {
    const resposta = await fetch('/api/status', {cache:'no-store'});
    const dados = await resposta.json();

    let ok = 0, err = 0, run = 0;

    document.getElementById('lista').innerHTML = dados.map(t => {
      const ultima = t.historico[t.historico.length-1];
      const status = t.rodando ? 'rodando' : (ultima ? ultima.status : 'nunca');
      const limite = Date.now()/1000 - 86400;

      t.historico.forEach(h => {
        if (h.inicio >= limite) {
          if (h.status === 'sucesso') ok++;
          else if (h.status === 'falha') err++;
        }
      });

      if (status === 'rodando') run++;

      const grade = t.historico.map(h =>
        `<button class="q ${esc(h.status)}"
          style="background:${cor[h.status] || 'var(--int)'}"
          title="${fmt(h.inicio)} · ${esc(h.status)} ${dur(h.dur)}"
          onclick="logExecucao(${h.id})"></button>`
      ).join('');

      const seletorModo = t.modos ? `
        <select id="modo-${encodeURIComponent(t.nome)}" ${t.rodando?'disabled':''}>
          ${t.modos.map(m => `
            <option value="${esc(m)}" ${m===t.modo_padrao?'selected':''}>
              ${esc(m.toUpperCase())}
            </option>
          `).join('')}
        </select>
      ` : '';

      return `
        <div class="card">
          <div class="topo">
            <div>
              <span class="nome">${esc(t.nome)}</span>
              <span class="badge ${status}">${esc(status)}</span>
              <div class="mut linha-info">
                ${descricaoAgendamento(t)}
                · última: ${fmt(ultima && ultima.inicio)}
                ${ultima ? '('+dur(ultima.dur)+')' : ''}
                ${t.proxima && !t.rodando ? ' · próxima: '+fmt(t.proxima) : ''}
              </div>
            </div>
            <div class="acoes">
              ${seletorModo}
              <button class="run" ${t.rodando?'disabled':''}
                onclick="executarAgora('${esc(t.nome)}')">
                ▶ Executar agora
              </button>
            </div>
          </div>
          <div class="grade">${grade}</div>
        </div>
      `;
    }).join('') || '<p class="mut">Nenhuma tarefa registrada.</p>';

    document.getElementById('resumo').innerHTML =
      `<div class="pill"><b style="color:var(--ok)">${ok}</b>execuções ok (24h)</div>
       <div class="pill"><b style="color:var(--err)">${err}</b>falhas (24h)</div>
       <div class="pill"><b style="color:var(--run)">${run}</b>rodando agora</div>`;

    document.getElementById('atual').textContent =
      'atualizado ' + new Date().toLocaleTimeString('pt-BR');

  } catch (erro) {
    document.getElementById('lista').innerHTML =
      '<p class="mut">Não foi possível carregar o monitor. Verifique o terminal.</p>';
    console.error(erro);
  }
}

async function executarAgora(nome) {
  const seletor = document.getElementById('modo-' + encodeURIComponent(nome));
  const dados = {};

  if (seletor) dados.modo = seletor.value;

  const resposta = await fetch('/api/executar/' + encodeURIComponent(nome), {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(dados)
  });

  const resultado = await resposta.json();

  if (!resultado.iniciada) {
    console.warn('A tarefa não foi iniciada. Ela pode já estar em execução ou o modo é inválido.');
  }

  carregar();
}

async function logExecucao(id) {
  const resposta = await fetch('/api/run/' + id);
  const resultado = await resposta.json();

  if (!resultado.id) return;

  document.getElementById('dt').textContent =
    resultado.tarefa + ' · #' + resultado.id;
  document.getElementById('dm').textContent =
    `${resultado.status} · início ${fmt(resultado.inicio)} · duração ${
      dur(resultado.fim ? resultado.fim-resultado.inicio : null)
    }`;
  document.getElementById('dl').textContent = resultado.log || '(sem saída)';
  dlg.showModal();
}

carregar();
setInterval(carregar, 3000);
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):

    def _enviar(self, corpo, tipo="application/json", codigo=200):
        dados = corpo if isinstance(corpo, bytes) else corpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path == "/":
            self._enviar(PAGINA, "text/html")
            return

        if self.path == "/api/status":
            self._enviar(json.dumps(_status(), ensure_ascii=False))
            return

        if self.path.startswith("/api/run/"):
            try:
                identificador = int(self.path.rsplit("/", 1)[1])
                _, rows = sql(
                    "SELECT * FROM runs WHERE id=?",
                    identificador,
                )
            except ValueError:
                rows = []

            if rows:
                self._enviar(json.dumps(dict(rows[0]), ensure_ascii=False))
            else:
                self._enviar("{}", codigo=404)
            return

        self._enviar("{}", codigo=404)

    def do_POST(self):
        if not self.path.startswith("/api/executar/"):
            self._enviar("{}", codigo=404)
            return

        nome = unquote(self.path.split("/api/executar/", 1)[1])

        if nome not in TAREFAS:
            self._enviar('{"erro":"Tarefa não encontrada"}', codigo=404)
            return

        try:
            tamanho = int(self.headers.get("Content-Length", 0))

            if tamanho > 10_000:
                self._enviar('{"erro":"Requisição muito grande"}', codigo=413)
                return

            corpo = self.rfile.read(tamanho) if tamanho else b"{}"
            parametros = json.loads(corpo.decode("utf-8"))

            if not isinstance(parametros, dict):
                raise ValueError("O corpo deve ser um objeto JSON.")

            modo = parametros.get("modo")
            modos = TAREFAS[nome].get("modos")

            if modos and modo is not None and modo not in modos:
                self._enviar('{"erro":"Modo inválido"}', codigo=400)
                return

            if not modos and modo is not None:
                self._enviar('{"erro":"Esta tarefa não recebe modo"}', codigo=400)
                return

            iniciada = executar(nome, modo)

            self._enviar(
                json.dumps({"iniciada": iniciada}),
            )

        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as erro:
            self._enviar(
                json.dumps({"erro": str(erro)}, ensure_ascii=False),
                codigo=400,
            )

    def log_message(self, *args):
        # Evita imprimir cada requisição HTTP no terminal.
        pass


def servir(porta=8000, host="127.0.0.1"):
    """Inicia o agendador e o painel web."""
    thread_agendador = threading.Thread(
        target=_agendador,
        daemon=True,
        name="agendador",
    )
    thread_agendador.start()

    endereco = "localhost" if host == "0.0.0.0" else host
    print(f"Painel em http://{endereco}:{porta}")

    try:
        servidor = ThreadingHTTPServer((host, porta), _Handler)
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando monitor...")
    finally:
        try:
            servidor.server_close()
        except UnboundLocalError:
            pass
        