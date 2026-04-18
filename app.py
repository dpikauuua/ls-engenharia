from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import json, os, random, string
from datetime import datetime

app = Flask(__name__)
app.secret_key = "ls_engenharia_secret_2024"

DB_FILE = "database.json"

def load_db():
    if not os.path.exists(DB_FILE):
        db = {
            "funcionarios": {
                "14160176402": {
                    "cpf": "141.601.764-02",
                    "nome": "RH - LS Engenharia",
                    "senha": "040807Ka-",
                    "role": "rh",
                    "ativo": True
                }
            },
            "pedidos": []
        }
        save_db(db)
    with open(DB_FILE) as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def gerar_senha():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=8))

def cpf_limpo(cpf):
    return cpf.replace(".", "").replace("-", "").replace(" ", "")

# ─── ROTAS ───────────────────────────────────────────────

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
    db = load_db()
    usuario = db["funcionarios"].get(cpf)
    if usuario and usuario["senha"] == senha and usuario["ativo"]:
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

# ─── PAINEL RH ───────────────────────────────────────────

@app.route("/rh")
def painel_rh():
    if session.get("role") != "rh":
        return redirect(url_for("index"))
    db = load_db()
    pedidos = sorted(db["pedidos"], key=lambda x: x["data"], reverse=True)
    funcionarios = {k: v for k, v in db["funcionarios"].items() if v["role"] != "rh"}
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
    db = load_db()
    if cpf_raw in db["funcionarios"]:
        flash("Funcionário já cadastrado.")
        return redirect(url_for("painel_rh"))
    senha = gerar_senha()
    cpf_fmt = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}"
    db["funcionarios"][cpf_raw] = {
        "cpf": cpf_fmt,
        "nome": nome,
        "senha": senha,
        "role": "funcionario",
        "ativo": True
    }
    save_db(db)
    flash(f"Funcionário {nome} cadastrado! Senha gerada: {senha}")
    return redirect(url_for("painel_rh"))

@app.route("/rh/pedido/<int:idx>/aceitar", methods=["POST"])
def aceitar_pedido(idx):
    if session.get("role") != "rh":
        return jsonify({"erro": "Sem permissão"}), 403
    db = load_db()
    if 0 <= idx < len(db["pedidos"]):
        db["pedidos"][idx]["status"] = "aprovado"
        db["pedidos"][idx]["data_resposta"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        save_db(db)
    return redirect(url_for("painel_rh"))

@app.route("/rh/pedido/<int:idx>/recusar", methods=["POST"])
def recusar_pedido(idx):
    if session.get("role") != "rh":
        return jsonify({"erro": "Sem permissão"}), 403
    db = load_db()
    if 0 <= idx < len(db["pedidos"]):
        db["pedidos"][idx]["status"] = "recusado"
        db["pedidos"][idx]["data_resposta"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        save_db(db)
    return redirect(url_for("painel_rh"))

@app.route("/rh/remover/<cpf>", methods=["POST"])
def remover_funcionario(cpf):
    if session.get("role") != "rh":
        return redirect(url_for("index"))
    db = load_db()
    if cpf in db["funcionarios"] and db["funcionarios"][cpf]["role"] != "rh":
        db["funcionarios"][cpf]["ativo"] = False
        save_db(db)
        flash("Funcionário removido.")
    return redirect(url_for("painel_rh"))

# ─── PAINEL FUNCIONÁRIO ──────────────────────────────────

@app.route("/funcionario")
def painel_funcionario():
    if "usuario" not in session or session.get("role") != "funcionario":
        return redirect(url_for("index"))
    db = load_db()
    cpf = session["usuario"]
    meus_pedidos = [p for p in db["pedidos"] if p["cpf"] == cpf]
    meus_pedidos = sorted(meus_pedidos, key=lambda x: x["data"], reverse=True)
    pendentes = [p for p in meus_pedidos if p["status"] == "pendente"]
    return render_template("funcionario.html", pedidos=meus_pedidos, nome=session["nome"],
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
    db = load_db()
    cpf = session["usuario"]
    pendentes = [p for p in db["pedidos"] if p["cpf"] == cpf and p["status"] == "pendente"]
    if pendentes:
        flash("Você já tem um pedido pendente.")
        return redirect(url_for("painel_funcionario"))
    db["pedidos"].append({
        "cpf": cpf,
        "nome": session["nome"],
        "valor": valor,
        "chave_pix": chave_pix,
        "motivo": motivo,
        "status": "pendente",
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_resposta": None
    })
    save_db(db)
    flash("Pedido enviado com sucesso!")
    return redirect(url_for("painel_funcionario"))

if __name__ == "__main__":
    load_db()
    print("\n✅ LS Engenharia - Sistema de Vale rodando!")
    print("🌐 Acesse: http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000, host='0.0.0.0')
    
