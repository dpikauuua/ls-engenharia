from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import os, random, string
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "ls_engenharia_secret_2024"

def get_db():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode="require")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS funcionarios (
            cpf VARCHAR(11) PRIMARY KEY,
            cpf_fmt VARCHAR(14),
            nome VARCHAR(200),
            senha VARCHAR(300),
            senha_legivel VARCHAR(50),
            role VARCHAR(20),
            ativo BOOLEAN DEFAULT TRUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            cpf VARCHAR(11),
            nome VARCHAR(200),
            valor FLOAT,
            chave_pix VARCHAR(200),
            motivo TEXT,
            status VARCHAR(20) DEFAULT 'pendente',
            data VARCHAR(20),
            data_resposta VARCHAR(20)
        )
    """)
    cur.execute("SELECT cpf FROM funcionarios WHERE cpf = '14160176402'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO funcionarios (cpf, cpf_fmt, nome, senha, role, ativo)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ('14160176402', '141.601.764-02', 'RH - LS Engenharia',
              generate_password_hash('040807Ka-'), 'rh', True))
    conn.commit()
    cur.close()
    conn.close()

def gerar_senha():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=8))

def cpf_limpo(cpf):
    return cpf.replace(".", "").replace("-", "").replace(" ", "")

@app.route("/")
def index():
    if "usuario" in session:
        if session.get("role") == "rh":
            return redirect(url_for("painel_rh"))
        return redirect(url_for("painel_funcionario"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    cpf = cpf_limpo(request.form.get("cpf", ""))
    senha = request.form.get("senha", "")
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM funcionarios WHERE cpf = %s AND ativo = TRUE", (cpf,))
    usuario = cur.fetchone()
    cur.close()
    conn.close()
    if usuario and check_password_hash(usuario["senha"], senha):
        session["usuario"] = cpf
        session["nome"] = usuario["nome"]
        session["role"] = usuario["role"]
        return redirect(url_for("painel_rh") if usuario["role"] == "rh" else url_for("painel_funcionario"))
    flash("CPF ou senha incorretos.")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/rh")
def painel_rh():
    if session.get("role") != "rh":
        return redirect(url_for("index"))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM pedidos ORDER BY id DESC")
    pedidos = cur.fetchall()
    cur.execute("SELECT * FROM funcionarios WHERE role != 'rh'")
    funcionarios = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("rh.html", pedidos=pedidos, funcionarios=funcionarios, nome=session["nome"])

@app.route("/rh/cadastrar", methods=["POST"])
def cadastrar_funcionario():
    if session.get("role") != "rh":
        return jsonify({"erro": "Sem permissão"}), 403
    cpf_raw = cpf_limpo(request.form.get("cpf", ""))
    nome = request.form.get("nome", "").strip()
    if not cpf_raw or not nome:
        flash("CPF e nome são obrigatórios.")
        return redirect(url_for("painel_rh"))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT cpf FROM funcionarios WHERE cpf = %s", (cpf_raw,))
    if cur.fetchone():
        flash("Funcionário já cadastrado.")
        cur.close()
        conn.close()
        return redirect(url_for("painel_rh"))
    senha = gerar_senha()
    cpf_fmt = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
    cur.execute("""
        INSERT INTO funcionarios (cpf, cpf_fmt, nome, senha, senha_legivel, role, ativo)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (cpf_raw, cpf_fmt, nome, generate_password_hash(senha), senha, 'funcionario', True))
    conn.commit()
    cur.close()
    conn.close()
    flash(f"Funcionário {nome} cadastrado! Senha gerada: {senha}")
    return redirect(url_for("painel_rh"))

@app.route("/rh/pedido/<int:idx>/aceitar", methods=["POST"])
def aceitar_pedido(idx):
    if session.get("role") != "rh":
        return jsonify({"erro": "Sem permissão"}), 403
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE pedidos SET status = 'aprovado', data_resposta = %s WHERE id = %s",
                (datetime.now().strftime("%d/%m/%Y %H:%M"), idx))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("painel_rh"))

@app.route("/rh/pedido/<int:idx>/recusar", methods=["POST"])
def recusar_pedido(idx):
    if session.get("role") != "rh":
        return jsonify({"erro": "Sem permissão"}), 403
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE pedidos SET status = 'recusado', data_resposta = %s WHERE id = %s",
                (datetime.now().strftime("%d/%m/%Y %H:%M"), idx))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("painel_rh"))

@app.route("/rh/remover/<cpf>", methods=["POST"])
def remover_funcionario(cpf):
    if session.get("role") != "rh":
        return redirect(url_for("index"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE funcionarios SET ativo = FALSE WHERE cpf = %s AND role != 'rh'", (cpf,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Funcionário removido.")
    return redirect(url_for("painel_rh"))

@app.route("/funcionario")
def painel_funcionario():
    if "usuario" not in session or session.get("role") != "funcionario":
        return redirect(url_for("index"))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM pedidos WHERE cpf = %s ORDER BY id DESC", (session["usuario"],))
    pedidos = cur.fetchall()
    cur.close()
    conn.close()
    pendentes = [p for p in pedidos if p["status"] == "pendente"]
    return render_template("funcionario.html", pedidos=pedidos, nome=session["nome"],
                           pode_pedir=len(pendentes) == 0)

@app.route("/funcionario/pedir", methods=["POST"])
def fazer_pedido():
    if session.get("role") != "funcionario":
        return redirect(url_for("index"))
    valor = float(request.form.get("valor", 0))
    chave_pix = request.form.get("chave_pix", "").strip()
    motivo = request.form.get("motivo", "").strip()
    if valor <= 0 or valor > 1000:
        flash("Valor inválido. Máximo R$ 1.000,00.")
        return redirect(url_for("painel_funcionario"))
    if not chave_pix or not motivo:
        flash("Chave Pix e motivo são obrigatórios.")
        return redirect(url_for("painel_funcionario"))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM pedidos WHERE cpf = %s AND status = 'pendente'", (session["usuario"],))
    if cur.fetchone():
        flash("Você já tem um pedido pendente.")
        cur.close()
        conn.close()
        return redirect(url_for("painel_funcionario"))
    cur.execute("""
        INSERT INTO pedidos (cpf, nome, valor, chave_pix, motivo, status, data)
        VALUES (%s, %s, %s, %s, %s, 'pendente', %s)
    """, (session["usuario"], session["nome"], valor, chave_pix, motivo,
          datetime.now().strftime("%d/%m/%Y %H:%M")))
    conn.commit()
    cur.close()
    conn.close()
    flash("Pedido enviado com sucesso!")
    return redirect(url_for("painel_funcionario"))

if __name__ == "__main__":
    init_db()
    print("\n✅ LS Engenharia - Sistema de Vale rodando!")
    print("🌐 Acesse: http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000, host='0.0.0.0')