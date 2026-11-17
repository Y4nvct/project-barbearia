from contextlib import closing

import pytest

import database
from operacoes import (
    cadastrar_servico,
    cadastrar_usuario,
    confirmar_pagamento,
    registrar_atendimento,
    resumo_diario,
)


@pytest.fixture
def dados_teste(tmp_path, monkeypatch):
    # Banco temporário: não altera o banco real
    monkeypatch.setattr(database, "BANCO", tmp_path / "teste.db")

    database.criar_tabelas()

    usuario = cadastrar_usuario("Usuario Teste", "teste", "SenhaTeste123!")
    servico = cadastrar_servico("Corte", 2500)

    return usuario, servico


def test_cadastro_usuario(dados_teste):
    usuario, _ = dados_teste

    with closing(database.conectar()) as banco:
        registro = banco.execute(
            "SELECT nome FROM usuario WHERE id_usuario = ?", (usuario,)
        ).fetchone()

    assert registro["nome"] == "Usuario Teste"


def test_cadastro_servico(dados_teste):
    _, servico = dados_teste

    with closing(database.conectar()) as banco:
        registro = banco.execute(
            """
            SELECT preco_padrao_centavos
            FROM servico WHERE id_servico = ?
            """,
            (servico,),
        ).fetchone()

    assert registro["preco_padrao_centavos"] == 2500


def test_atendimento_pago(dados_teste):
    usuario, servico = dados_teste
    registrar_atendimento(servico, usuario, "PAGO")

    resumo = resumo_diario()

    assert resumo["atendimentos_dia"] == 1
    assert resumo["recebido_centavos"] == 2500


def test_atendimento_pendente(dados_teste):
    usuario, servico = dados_teste

    registrar_atendimento(servico, usuario, "PENDENTE", "Cliente Teste")

    resumo = resumo_diario()

    assert resumo["pendente_total_centavos"] == 2500
    assert resumo["recebido_centavos"] == 0


def test_confirmacao_pagamento(dados_teste):
    usuario, servico = dados_teste

    atendimento = registrar_atendimento(servico, usuario, "PENDENTE", "Cliente Teste")

    confirmar_pagamento(atendimento)

    resumo = resumo_diario()

    assert resumo["pendente_total_centavos"] == 0
    assert resumo["recebido_centavos"] == 2500


def test_pendencia_sem_cliente(dados_teste):
    usuario, servico = dados_teste

    with pytest.raises(ValueError):
        registrar_atendimento(servico, usuario, "PENDENTE")
