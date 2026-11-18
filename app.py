
import os
import secrets
from contextlib import closing

from flask import (
    Flask, abort, flash, get_flashed_messages,
    redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash

from database import conectar, criar_tabelas
from operacoes import (
    confirmar_pagamento,
    registrar_atendimento,
    resumo_diario
)

app = Flask(__name__)

app.secret_key = (
    os.environ.get("SECRET_KEY")
    or secrets.token_hex(32)
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

def moeda(centavos):
    valor = f"{centavos / 100:,.2f}"
    valor = valor.replace(",", "X")
    valor = valor.replace(".", ",").replace("X", ".")
    return f"R$ {valor}"


@app.before_request
def verificar_acesso():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    if request.method == "POST":
        recebido = request.form.get("csrf_token", "")
        esperado = session["csrf_token"]

        if not secrets.compare_digest(recebido, esperado):
            abort(400)

    if request.endpoint in ("entrar", "static"):
        return None

    if "usuario_id" not in session:
        return redirect(url_for("entrar"))


@app.route("/login", methods=["GET", "POST"])
def entrar():
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        senha = request.form.get("senha", "")

        with closing(conectar()) as banco:
            usuario = banco.execute(
                """
                SELECT id_usuario, senha_hash
                FROM usuario
                WHERE login = ? AND ativo = 1
                """,
                (login,)
            ).fetchone()

        if usuario and check_password_hash(
            usuario["senha_hash"], senha
        ):
            session.clear()
            session["usuario_id"] = usuario["id_usuario"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("inicio"))

        flash("Login ou senha inválidos.")

    mensagens = get_flashed_messages()

    return render_template(
        "login.html",
        mensagem=mensagens[-1] if mensagens else None,
        csrf_token=session["csrf_token"]
    )


@app.route("/")
def inicio():
    with closing(conectar()) as banco:
        servicos = banco.execute(
            """
            SELECT id_servico, nome
            FROM servico
            WHERE ativo = 1
            ORDER BY nome
            """
        ).fetchall()

        pendencias = banco.execute(
            """
            SELECT
                id_atendimento,
                referencia_cliente,
                valor_cobrado_centavos
            FROM atendimento
            WHERE status_pagamento = 'PENDENTE'
            ORDER BY id_atendimento DESC
            """
        ).fetchall()

    mensagens = get_flashed_messages()

    return render_template(
        "index.html",
        resumo=resumo_diario(),
        servicos=servicos,
        pendencias=pendencias,
        moeda=moeda,
        csrf_token=session["csrf_token"],
        mensagem=mensagens[-1] if mensagens else None
    )


@app.route("/atendimentos", methods=["POST"])
def novo_atendimento():
    try:
        id_servico = int(request.form.get("id_servico", ""))

        registrar_atendimento(
            id_servico=id_servico,
            id_usuario=session["usuario_id"],
            status_pagamento=request.form.get(
                "status_pagamento", ""
            ),
            referencia_cliente=request.form.get(
                "referencia_cliente", ""
            )
        )

        flash("Atendimento registrado com sucesso.")

    except ValueError as erro:
        flash(str(erro))

    return redirect(url_for("inicio"))


@app.route(
    "/pagamentos/<int:id_atendimento>/confirmar",
    methods=["POST"]
)
def pagar_atendimento(id_atendimento):
    try:
        confirmar_pagamento(id_atendimento)
        flash("Pagamento confirmado com sucesso.")

    except ValueError as erro:
        flash(str(erro))

    return redirect(url_for("inicio"))


@app.route("/sair", methods=["POST"])
def sair():
    session.clear()
    return redirect(url_for("entrar"))


if __name__ == "__main__":
    criar_tabelas()
    app.run(debug=False)

