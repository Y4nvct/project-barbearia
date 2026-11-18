from contextlib import closing
from datetime import date

import pytest

import app as sistema
import configurar
import database
from operacoes import cadastrar_servico, cadastrar_usuario


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database, "BANCO", tmp_path / "integracao.db"
    )

    database.criar_tabelas()
    cadastrar_usuario("Operador Teste", "operador", "SenhaTeste123!")
    cadastrar_servico("Corte teste", 2500)

    sistema.app.config.update(
        TESTING=True,
        SECRET_KEY="chave-exclusiva-para-testes"
    )

    with sistema.app.test_client() as navegador:
        yield navegador


def fazer_login(cliente):
    cliente.get("/login")

    with cliente.session_transaction() as sessao:
        token = sessao["csrf_token"]

    resposta = cliente.post(
        "/login",
        data={
            "login": "operador",
            "senha": "SenhaTeste123!",
            "csrf_token": token
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200

    with cliente.session_transaction() as sessao:
        return sessao["csrf_token"]


def test_redireciona_usuario_sem_login(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_exibe_tela_login(cliente):
    resposta = cliente.get("/login")
    assert resposta.status_code == 200
    assert b"Entrar no sistema" in resposta.data


def test_login_valido(cliente):
    fazer_login(cliente)

    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert f"Resumo de {date.today():%d/%m/%Y}" in resposta.get_data(as_text=True)


def test_registro_pago_pela_interface(cliente):
    token = fazer_login(cliente)

    resposta = cliente.post(
        "/atendimentos",
        data={
            "id_servico": "1",
            "status_pagamento": "PAGO",
            "csrf_token": token
        },
        follow_redirects=True
    )

    assert resposta.status_code == 200
    assert b"Atendimento registrado" in resposta.data


def test_pagamento_pendente_pela_interface(cliente):
    token = fazer_login(cliente)

    cliente.post(
        "/atendimentos",
        data={
            "id_servico": "1",
            "status_pagamento": "PENDENTE",
            "referencia_cliente": "Cliente Teste",
            "csrf_token": token
        }
    )

    resposta = cliente.post(
        "/pagamentos/1/confirmar",
        data={"csrf_token": token},
        follow_redirects=True
    )

    assert resposta.status_code == 200
    assert b"Pagamento confirmado" in resposta.data


def test_rejeita_formulario_sem_csrf(cliente):
    fazer_login(cliente)

    resposta = cliente.post(
        "/atendimentos",
        data={
            "id_servico": "1",
            "status_pagamento": "PAGO"
        }
    )

    assert resposta.status_code == 400


def test_configuracao_inicial(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database, "BANCO", tmp_path / "configuracao.db"
    )

    respostas = iter([
        "Operador Teste",
        "admin",
        "Corte",
        "25,00",
        ""
    ])

    monkeypatch.setattr(
        "builtins.input",
        lambda mensagem: next(respostas)
    )

    monkeypatch.setattr(
        configurar,
        "getpass",
        lambda mensagem: "SenhaTeste123!"
    )

    configurar.configurar()

    with closing(database.conectar()) as banco:
        usuarios = banco.execute(
            "SELECT COUNT(*) FROM usuario"
        ).fetchone()[0]

        servicos = banco.execute(
            "SELECT COUNT(*) FROM servico"
        ).fetchone()[0]

    assert usuarios == 1
    assert servicos == 1


def test_calendario_consulta_data_e_compara_dia_anterior(cliente):
    from flask import template_rendered

    fazer_login(cliente)
    with closing(database.conectar()) as banco:
        with banco:
            banco.executemany(
                """INSERT INTO atendimento
                   (id_servico, id_usuario, data_atendimento,
                    valor_cobrado_centavos, status_pagamento, data_pagamento)
                   VALUES (1, 1, ?, 2500, ?, ?)""",
                [
                    ("2026-11-17T10:00:00-03:00", "PAGO", "2026-11-17T10:00:00-03:00"),
                    ("2026-11-18T10:00:00-03:00", "PAGO", "2026-11-18T10:00:00-03:00"),
                    ("2026-11-18T11:00:00-03:00", "PENDENTE", None),
                ],
            )

    contextos = []

    def capturar(sender, template, context, **extras):
        contextos.append(context)

    template_rendered.connect(capturar, sistema.app)
    try:
        resposta = cliente.get("/?data=2026-11-18")
    finally:
        template_rendered.disconnect(capturar, sistema.app)

    assert resposta.status_code == 200
    texto = resposta.get_data(as_text=True)
    assert "Resumo de 18/11/2026" in texto
    assert "Comparação com 17/11/2026" in texto
    assert 'value="2026-11-18"' in texto
    contexto = contextos[-1]
    assert contexto["resumo"] == {
        "atendimentos_dia": 2, "recebido_centavos": 2500,
        "pendente_total_centavos": 2500,
    }
    assert contexto["resumo_anterior"] == {
        "atendimentos_dia": 1, "recebido_centavos": 2500,
        "pendente_total_centavos": 2500,
    }


@pytest.mark.parametrize("data_consulta", ["", "invalida", "0001-01-01"])
def test_calendario_data_invalida_exibe_dia_atual(cliente, data_consulta):
    fazer_login(cliente)
    resposta = cliente.get("/", query_string={"data": data_consulta})
    assert resposta.status_code == 200
    texto = resposta.get_data(as_text=True)
    assert "Data inválida. Exibindo o dia atual." in texto
    assert f"Resumo de {date.today():%d/%m/%Y}" in texto
