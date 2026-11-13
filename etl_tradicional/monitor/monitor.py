"""
monitor.py - mini "Airflow" sem complexidade: agenda, executa e monitora tarefas Python.

- Só biblioteca padrão (nada para instalar)
- Histórico em SQLite (monitor.db)
- Painel web com auto-atualização, logs por execução e botão "Executar agora"

Uso (veja tarefas.py):
    from monitor import tarefa, servir

    @tarefa(every=300, retries=2)      # a cada 5 min, até 2 novas tentativas
    def minha_tarefa():
        print("isso aparece no log da execução")

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

AQUI = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(AQUI, "monitor.db")
RETENCAO_DIAS = 30
HISTORICO = 30  # quantas execuções aparecem por tarefa no painel

TAREFAS = {}  # nome -> dict(fn, every, retries, next, running)

# ---------------------------------------------------------------- banco ----
_lock = threading.Lock()
_con = sqlite3.connect(DB, check_same_thread=False)
_con.row_factory = sqlite3.Row
_con.execute(
    "CREATE TABLE IF NOT EXISTS runs("
    "id INTEGER PRIMARY KEY, tarefa TEXT, status TEXT, inicio REAL, fim REAL, log TEXT)"
)
_con.execute("CREATE INDEX IF NOT EXISTS ix_runs ON runs(tarefa, id)")
# execuções que ficaram "rodando" porque o processo anterior caiu
_con.execute("UPDATE runs SET status='interrompida', fim=inicio WHERE status='rodando'")
_con.commit()


def sql(query, *args):
    with _lock:
        cur = _con.execute(query, args)
        _con.commit()
        return cur.lastrowid, cur.fetchall() if cur.description else []


# ------------------------------------------- captura de print() por thread ----
_local = threading.local()


class _Saida:
    """Substitui sys.stdout: copia o que cada tarefa imprime para o log dela."""

    def __init__(self, original):
        self.original = original

    def write(self, texto):
        self.original.write(texto)
        buf = getattr(_local, "buf", None)
        if buf is not None:
            buf.write(texto)
            # salva o log parcial a cada ~1s para acompanhar execuções longas ao vivo
            agora = time.time()
            if agora - _local.salvo > 1:
                _local.salvo = agora
                sql("UPDATE runs SET log=? WHERE id=?", buf.getvalue(), _local.rid)

    def flush(self):
        self.original.flush()


sys.stdout = _Saida(sys.stdout)

# ------------------------------------------------------------- execução ----


def tarefa(every=None, retries=0, nome=None):
    """Registra uma função. every=segundos entre execuções (None = só manual)."""

    def deco(fn):
        TAREFAS[nome or fn.__name__] = dict(
            fn=fn, every=every, retries=retries, next=time.time(), running=False
        )
        return fn

    return deco


def _python_do_projeto(pasta):
    """Usa o venv do projeto (.venv ou venv) se existir; senão, o Python atual."""
    for venv in (".venv", "venv"):
        for sub in ("bin/python", "Scripts/python.exe"):
            p = os.path.join(pasta, venv, sub)
            if os.path.exists(p):
                return p
    return sys.executable


class ErroProjeto(Exception):
    """Falha de projeto (exit code != 0 ou timeout): o log do próprio projeto já explica."""


def projeto(pasta, every=None, retries=0, timeout=None, nome=None, script="src/etl.py"):
    """
    Registra um projeto: roda `python src/etl.py` com a pasta do projeto como diretório de trabalho, como subprocesso.
    - usa o venv do projeto, se houver (pasta/.venv)
    - timeout em segundos (None = sem limite); estourou -> mata o processo e conta como falha
    - o que o script imprime vira o log da execução
    """
    pasta = os.path.abspath(pasta)
    nome = nome or os.path.basename(pasta)

    def rodar():
        cmd = [_python_do_projeto(pasta), "-u", script]
        print(f"$ {' '.join(cmd)}   (em {pasta})")
        proc = subprocess.Popen(
            cmd, cwd=pasta, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace",
        )
        estourou = []
        timer = None
        if timeout:
            def matar():
                estourou.append(1)
                proc.kill()
            timer = threading.Timer(timeout, matar)
            timer.start()
        try:
            for linha in proc.stdout:
                print(linha, end="")
            codigo = proc.wait()
        finally:
            if timer:
                timer.cancel()
            if proc.poll() is None:
                proc.kill()
        if estourou:
            raise ErroProjeto(f"excedeu o timeout de {timeout}s")
        if codigo != 0:
            raise ErroProjeto(f"{script} terminou com código {codigo}")

    TAREFAS[nome] = dict(fn=rodar, every=every, retries=retries, next=time.time(), running=False)


def executar(nome):
    """Dispara a tarefa em segundo plano. Ignora se já estiver rodando."""
    t = TAREFAS[nome]
    with _lock:
        if t["running"]:
            return False
        t["running"] = True
    threading.Thread(target=_rodar, args=(nome,), daemon=True).start()
    return True


def _rodar(nome):
    t = TAREFAS[nome]
    rid, _ = sql("INSERT INTO runs(tarefa,status,inicio) VALUES(?,?,?)", nome, "rodando", time.time())
    _local.buf = io.StringIO()
    _local.rid, _local.salvo = rid, 0
    status = "falha"
    try:
        for tentativa in range(t["retries"] + 1):
            try:
                if tentativa:
                    print(f"--- tentativa {tentativa + 1} de {t['retries'] + 1} ---")
                t["fn"]()
                status = "sucesso"
                break
            except ErroProjeto as e:
                print(f"[monitor] {e}")
                time.sleep(min(5 * (tentativa + 1), 30))
            except Exception:
                print(traceback.format_exc())
                time.sleep(min(5 * (tentativa + 1), 30))
    finally:
        log = _local.buf.getvalue()
        _local.buf = None
        sql("UPDATE runs SET status=?, fim=?, log=? WHERE id=?", status, time.time(), log, rid)
        t["running"] = False


def _agendador():
    ultima_limpeza = 0
    while True:
        agora = time.time()
        for nome, t in TAREFAS.items():
            if t["every"] and agora >= t["next"]:
                t["next"] = agora + t["every"]
                executar(nome)
        if agora - ultima_limpeza > 3600:
            sql("DELETE FROM runs WHERE inicio < ?", agora - RETENCAO_DIAS * 86400)
            ultima_limpeza = agora
        time.sleep(1)


# ------------------------------------------------------------------ web ----


def _status():
    saida = []
    for nome, t in TAREFAS.items():
        _, rows = sql(
            "SELECT id,status,inicio,fim FROM runs WHERE tarefa=? ORDER BY id DESC LIMIT ?",
            nome, HISTORICO,
        )
        hist = [
            dict(id=r["id"], status=r["status"], inicio=r["inicio"],
                 dur=(r["fim"] - r["inicio"]) if r["fim"] else None)
            for r in reversed(rows)
        ]
        saida.append(dict(
            nome=nome, every=t["every"], rodando=t["running"],
            proxima=t["next"] if t["every"] else None, historico=hist,
        ))
    return saida


PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de tarefas</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--tx:#1d2330;--mut:#6b7385;--bd:#e3e6ec;
--ok:#2e9e5b;--err:#d64545;--run:#e0a21b;--int:#9aa1b0}
@media(prefers-color-scheme:dark){:root{--bg:#14171d;--card:#1d222b;--tx:#e8eaf0;--mut:#8b93a5;--bd:#2c3340}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,sans-serif}
main{max-width:1000px;margin:0 auto;padding:20px 16px}
header{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
h1{font-size:20px;margin:0}
.mut{color:var(--mut);font-size:13px}
.resumo{display:flex;gap:10px;margin:16px 0;flex-wrap:wrap}
.pill{background:var(--card);border:1px solid var(--bd);border-radius:8px;padding:8px 14px}
.pill b{font-size:18px;margin-right:6px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px 16px;margin-bottom:10px}
.topo{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.nome{font-weight:600}
.badge{font-size:12px;padding:2px 8px;border-radius:10px;color:#fff;margin-left:8px}
.sucesso{background:var(--ok)}.falha{background:var(--err)}.rodando{background:var(--run)}
.interrompida{background:var(--int)}.nunca{background:var(--int)}
.grade{display:flex;gap:3px;margin-top:10px;flex-wrap:wrap}
.q{width:16px;height:16px;border-radius:3px;cursor:pointer;border:0;padding:0}
.q.rodando{animation:p 1s infinite}@keyframes p{50%{opacity:.4}}
button.run{background:none;border:1px solid var(--bd);color:var(--tx);border-radius:6px;padding:5px 12px;cursor:pointer}
button.run:hover:not(:disabled){border-color:var(--tx)}button.run:disabled{opacity:.4;cursor:default}
dialog{width:min(800px,94vw);background:var(--card);color:var(--tx);border:1px solid var(--bd);border-radius:10px}
dialog::backdrop{background:#0008}
pre{background:var(--bg);padding:12px;border-radius:6px;overflow:auto;max-height:55vh;font-size:13px;white-space:pre-wrap}
</style></head><body><main>
<header><h1>Monitor de tarefas</h1><span class="mut" id="atual"></span></header>
<div class="resumo" id="resumo"></div>
<div id="lista"></div>
<dialog id="dlg"><div class="topo"><b id="dt"></b><button class="run" onclick="dlg.close()">Fechar</button></div>
<p class="mut" id="dm"></p><pre id="dl"></pre></dialog>
</main>
<script>
const dlg=document.getElementById('dlg');
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=t=>t?new Date(t*1000).toLocaleString('pt-BR'):'—';
const dur=s=>s==null?'':s<60?s.toFixed(1)+'s':Math.floor(s/60)+'min '+Math.round(s%60)+'s';
const cor={sucesso:'var(--ok)',falha:'var(--err)',rodando:'var(--run)',interrompida:'var(--int)'};
const intervalo=s=>!s?'manual':s%3600==0?`a cada ${s/3600}h`:s%60==0?`a cada ${s/60}min`:`a cada ${s}s`;

async function carregar(){
  const d=await (await fetch('/api/status')).json();
  let ok=0,err=0,run=0;
  document.getElementById('lista').innerHTML=d.map(t=>{
    const u=t.historico[t.historico.length-1];
    const st=t.rodando?'rodando':(u?u.status:'nunca');
    const lim=Date.now()/1000-86400;
    t.historico.forEach(h=>{if(h.inicio>=lim){if(h.status=='sucesso')ok++;else if(h.status=='falha')err++;}});
    if(st=='rodando')run++;
    const grade=t.historico.map(h=>`<button class="q ${h.status}" style="background:${cor[h.status]}"
      title="${fmt(h.inicio)} · ${h.status} ${dur(h.dur)}" onclick="log(${h.id})"></button>`).join('');
    return `<div class="card"><div class="topo">
      <div><span class="nome">${esc(t.nome)}</span><span class="badge ${st}">${st}</span>
      <div class="mut">${intervalo(t.every)} · última: ${fmt(u&&u.inicio)} ${u?'('+dur(u.dur)+')':''}
      ${t.proxima&&!t.rodando?' · próxima: '+fmt(t.proxima):''}</div></div>
      <button class="run" ${t.rodando?'disabled':''} onclick="exec('${esc(t.nome)}')">▶ Executar agora</button>
      </div><div class="grade">${grade}</div></div>`;
  }).join('')||'<p class="mut">Nenhuma tarefa registrada.</p>';
  document.getElementById('resumo').innerHTML=
    `<div class="pill"><b style="color:var(--ok)">${ok}</b>execuções ok (24h)</div>
     <div class="pill"><b style="color:var(--err)">${err}</b>falhas (24h)</div>
     <div class="pill"><b style="color:var(--run)">${run}</b>rodando agora</div>`;
  document.getElementById('atual').textContent='atualizado '+new Date().toLocaleTimeString('pt-BR');
}
async function exec(n){await fetch('/api/executar/'+encodeURIComponent(n),{method:'POST'});carregar();}
async function log(id){
  const r=await (await fetch('/api/run/'+id)).json();
  dt.textContent=r.tarefa+' · #'+r.id;
  dm.textContent=`${r.status} · início ${fmt(r.inicio)} · duração ${dur(r.fim?r.fim-r.inicio:null)}`;
  dl.textContent=r.log||'(sem saída)';dlg.showModal();
}
carregar();setInterval(carregar,3000);
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def _enviar(self, corpo, tipo="application/json", codigo=200):
        dados = corpo if isinstance(corpo, bytes) else corpo.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path == "/":
            self._enviar(PAGINA, "text/html")
        elif self.path == "/api/status":
            self._enviar(json.dumps(_status()))
        elif self.path.startswith("/api/run/"):
            try:
                _, rows = sql("SELECT * FROM runs WHERE id=?", int(self.path.rsplit("/", 1)[1]))
            except ValueError:
                rows = []
            if rows:
                self._enviar(json.dumps(dict(rows[0])))
            else:
                self._enviar("{}", codigo=404)
        else:
            self._enviar("{}", codigo=404)

    def do_POST(self):
        if self.path.startswith("/api/executar/"):
            nome = unquote(self.path.split("/api/executar/", 1)[1])
            if nome in TAREFAS:
                self._enviar(json.dumps(dict(iniciada=executar(nome))))
                return
        self._enviar("{}", codigo=404)

    def log_message(self, *a):  # silencia o log de cada requisição
        pass


def servir(porta=8000, host="127.0.0.1"):
    """Inicia o agendador e o painel. Use host='0.0.0.0' para acessar de outras máquinas."""
    threading.Thread(target=_agendador, daemon=True).start()
    print(f"Painel em http://{host if host != '0.0.0.0' else 'localhost'}:{porta}")
    try:
        ThreadingHTTPServer((host, porta), _Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
