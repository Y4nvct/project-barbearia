from contextlib import closing
from datetime import datetime
import sqlite3

import pytest

import database
from app import app
from estoque import (
    cadastrar_produto,
    listar_movimentacoes,
    listar_produtos,
    movimentar_estoque,
)
from operacoes import abrir_banco


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BANCO", tmp_path / "estoque.db")
    database.criar_tabelas()


@pytest.fixture
def cliente():
    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 1
            sessao["csrf_token"] = "teste"
        yield cliente


def estado_banco():
    # Nova conexão: verifica os dados efetivamente persistidos.
    with closing(database.conectar()) as banco:
        return (
            [tuple(r) for r in banco.execute("SELECT * FROM produto ORDER BY id_produto")],
            [tuple(r) for r in banco.execute(
                "SELECT * FROM movimentacao_estoque ORDER BY id_movimentacao"
            )],
        )


def test_historico_vazio(cliente):
    assert listar_movimentacoes() == []
    resposta = cliente.get("/estoque")
    assert resposta.status_code == 200
    assert "Nenhuma movimentação registrada." in resposta.get_data(as_text=True)


def test_entradas_saidas_e_historico_persistido():
    produto = cadastrar_produto("Shampoo", "ml", 2)
    movimentar_estoque(produto, "ENTRADA", 10, " Compra ")
    movimentar_estoque(produto, "SAIDA", 3)

    assert listar_produtos()[0]["quantidade"] == 7
    movimentos = listar_movimentacoes()
    assert len(movimentos) == 2
    assert [m["tipo"] for m in movimentos] == ["SAIDA", "ENTRADA"]
    assert [m["quantidade"] for m in movimentos] == [3, 10]
    assert [m["observacao"] for m in movimentos] == [None, "Compra"]
    for movimento in movimentos:
        assert movimento["id_produto"] == produto
        assert movimento["nome"] == "Shampoo"
        assert movimento["unidade"] == "ml"
        assert datetime.fromisoformat(movimento["data_movimentacao"]).tzinfo is not None


def test_ordem_por_instante_e_desempate_por_id():
    produto = cadastrar_produto("Creme", "g")
    datas = [
        "2026-11-18T10:00:00-03:00",  # 13h UTC: mais recente
        "2026-11-18T14:00:00+02:00",  # 12h UTC
        "2026-11-18T10:00:00-03:00",  # empate: maior ID primeiro
        "2026-11-17 23:59:59",  # formato SQLite sem fuso
    ]
    with abrir_banco() as banco:
        for data in datas:
            banco.execute(
                """INSERT INTO movimentacao_estoque
                   (id_produto, tipo, quantidade, data_movimentacao)
                   VALUES (?, 'ENTRADA', 1, ?)""",
                (produto, data),
            )
    assert [m["id_movimentacao"] for m in listar_movimentacoes()] == [3, 1, 2, 4]


def test_consulta_preserva_dados_e_inclui_produto_inativo():
    produto = cadastrar_produto("Produto antigo", "cx")
    movimentar_estoque(produto, "ENTRADA", 4)
    with abrir_banco() as banco:
        banco.execute("UPDATE produto SET ativo = 0 WHERE id_produto = ?", (produto,))
    antes = estado_banco()
    assert listar_produtos() == []
    movimento = listar_movimentacoes()[0]
    assert (movimento["nome"], movimento["unidade"]) == ("Produto antigo", "cx")
    assert estado_banco() == antes


@pytest.mark.parametrize("tipo,quantidade", [
    ("SAIDA", 8), ("SAIDA", 0), ("SAIDA", -1), ("SAIDA", True),
    ("SAIDA", 1.5), ("INVALIDO", 1),
])
def test_movimentacao_rejeitada_nao_altera_saldo_nem_historico(tipo, quantidade):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 10)
    movimentar_estoque(produto, "SAIDA", 3)
    antes = estado_banco()
    with pytest.raises(ValueError):
        movimentar_estoque(produto, tipo, quantidade)
    assert estado_banco() == antes


def test_produto_inexistente_ou_inativo_nao_gera_movimento():
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    with abrir_banco() as banco:
        banco.execute("UPDATE produto SET ativo = 0 WHERE id_produto = ?", (produto,))
    antes = estado_banco()
    for identificador in (produto, produto + 1):
        with pytest.raises(ValueError, match="Produto não encontrado"):
            movimentar_estoque(identificador, "SAIDA", 1)
    assert estado_banco() == antes


@pytest.mark.parametrize("tipo", ["ENTRADA", "SAIDA"])
def test_falha_ao_gravar_historico_desfaz_alteracao_de_saldo(tipo):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    with abrir_banco() as banco:
        banco.execute("""CREATE TRIGGER rejeitar_movimento
            BEFORE INSERT ON movimentacao_estoque
            BEGIN SELECT RAISE(ABORT, 'falha simulada'); END""")
    antes = estado_banco()
    with pytest.raises(sqlite3.IntegrityError, match="falha simulada"):
        movimentar_estoque(produto, tipo, 1)
    assert estado_banco() == antes


def test_saida_do_saldo_inteiro():
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    movimentar_estoque(produto, "SAIDA", 7)
    assert listar_produtos()[0]["quantidade"] == 0
    assert len(listar_movimentacoes()) == 2


def test_pagina_exibe_historico_e_rejeita_saida_sem_saldo(cliente):
    produto = cadastrar_produto("Shampoo <teste>", "ml")
    for tipo, quantidade, observacao in (
        ("ENTRADA", 10, "Compra antiga"),
        ("SAIDA", 3, "<script>alert(1)</script>"),
    ):
        resposta = cliente.post("/estoque/movimentacoes", data={
            "csrf_token": "teste", "id_produto": produto,
            "tipo": tipo, "quantidade": quantidade, "observacao": observacao,
        }, follow_redirects=True)
        assert resposta.status_code == 200
    antes = estado_banco()
    resposta = cliente.post("/estoque/movimentacoes", data={
        "csrf_token": "teste", "id_produto": produto,
        "tipo": "SAIDA", "quantidade": 8,
    }, follow_redirects=True)
    texto = resposta.get_data(as_text=True)
    assert "Estoque insuficiente para a saída." in texto
    historico = texto.split('id="historico-movimentacoes"', 1)[1]
    assert "Shampoo &lt;teste&gt;" in historico
    assert "3 ml" in historico and "10 ml" in historico
    assert "Entrada" in historico and "Saída" in historico
    assert '<time datetime="' in historico
    assert historico.index("&lt;script&gt;") < historico.index("Compra antiga")
    assert "<script>alert(1)</script>" not in historico
    assert estado_banco() == antes
