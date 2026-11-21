from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest.mock import patch

import pytest

import app as sistema
import database
from estoque import (
    cadastrar_produto,
    listar_movimentacoes,
    listar_produtos,
    movimentar_estoque,
)

MAX_SQLITE = 9223372036854775807


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BANCO", tmp_path / "regressao.db")
    database.criar_tabelas()


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setitem(sistema.app.config, "TESTING", True)
    with sistema.app.test_client() as navegador:
        with navegador.session_transaction() as sessao:
            sessao["usuario_id"] = 1
            sessao["csrf_token"] = "token-ascii-valido"
        yield navegador


def estado_estoque():
    with closing(database.conectar()) as banco:
        return (
            [
                tuple(r)
                for r in banco.execute("SELECT * FROM produto ORDER BY id_produto")
            ],
            [
                tuple(r)
                for r in banco.execute(
                    "SELECT * FROM movimentacao_estoque ORDER BY id_movimentacao"
                )
            ],
        )


@pytest.mark.parametrize(
    "minimo",
    [MAX_SQLITE + 1, MAX_SQLITE * 2, 10**1000],
    ids=["limite-mais-um", "dobro", "mil-digitos"],
)
def test_minimo_acima_do_limite_nao_cadastra(minimo):
    produto = cadastrar_produto("Existente")
    movimentar_estoque(produto, "ENTRADA", 7)
    antes = estado_estoque()
    with pytest.raises(ValueError, match="estoque mínimo"):
        cadastrar_produto("Novo", estoque_minimo=minimo)
    assert estado_estoque() == antes


@pytest.mark.parametrize("tipo", ["ENTRADA", "SAIDA"])
@pytest.mark.parametrize(
    "quantidade", [MAX_SQLITE + 1, 10**1000], ids=["limite-mais-um", "mil-digitos"]
)
def test_quantidade_acima_do_limite_preserva_saldo_e_historico(tipo, quantidade):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    antes = estado_estoque()
    with pytest.raises(ValueError, match="quantidade"):
        movimentar_estoque(produto, tipo, quantidade)
    assert estado_estoque() == antes


@pytest.mark.parametrize("tipo", ["ENTRADA", "SAIDA"])
def test_id_acima_do_limite_rejeitado_sem_mudancas(tipo):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    antes = estado_estoque()
    with pytest.raises(ValueError, match="Produto inválido"):
        movimentar_estoque(MAX_SQLITE + 1, tipo, 1)
    assert estado_estoque() == antes


def test_limite_exato_aceito_e_saldo_continua_inteiro():
    produto = cadastrar_produto("Shampoo", estoque_minimo=MAX_SQLITE)
    movimentar_estoque(produto, "ENTRADA", MAX_SQLITE - 1)
    movimentar_estoque(produto, "ENTRADA", 1)
    with closing(database.conectar()) as banco:
        saldo = banco.execute(
            "SELECT quantidade, typeof(quantidade) FROM produto WHERE id_produto = ?",
            (produto,),
        ).fetchone()
    assert tuple(saldo) == (MAX_SQLITE, "integer")
    assert listar_produtos()[0]["estoque_minimo"] == MAX_SQLITE
    movimentar_estoque(produto, "SAIDA", 1)
    assert listar_produtos()[0]["quantidade"] == MAX_SQLITE - 1
    assert len(listar_movimentacoes()) == 3


@pytest.mark.parametrize("saldo,entrada", [(MAX_SQLITE, 1), (MAX_SQLITE - 1, 2)])
def test_transbordamento_nao_altera_saldo_nem_historico(saldo, entrada):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", saldo)
    antes = estado_estoque()
    with pytest.raises(ValueError, match="limite máximo"):
        movimentar_estoque(produto, "ENTRADA", entrada)
    assert estado_estoque() == antes


def test_entradas_simultaneas_nao_ultrapassam_limite():
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", MAX_SQLITE - 1)
    barreira = Barrier(2)

    def registrar():
        barreira.wait(timeout=10)
        try:
            movimentar_estoque(produto, "ENTRADA", 1)
            return "registrada"
        except ValueError as erro:
            assert "limite máximo" in str(erro)
            return "rejeitada"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(registrar) for _ in range(2)]
        resultados = [futuro.result(timeout=15) for futuro in futuros]

    assert sorted(resultados) == ["registrada", "rejeitada"]
    assert listar_produtos()[0]["quantidade"] == MAX_SQLITE
    assert len(listar_movimentacoes()) == 2


@pytest.mark.parametrize("rota", ["/estoque/produtos", "/estoque/movimentacoes"])
@pytest.mark.parametrize("token", [None, "", "incorreto", "á", "token-🔒"])
def test_csrf_ausente_invalido_ou_nao_ascii_retorna_400(cliente, rota, token):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    antes = estado_estoque()
    dados = {
        "nome": "Novo",
        "unidade": "un",
        "estoque_minimo": "0",
        "id_produto": str(produto),
        "tipo": "ENTRADA",
        "quantidade": "1",
    }
    if token is not None:
        dados["csrf_token"] = token
    assert cliente.post(rota, data=dados).status_code == 400
    assert estado_estoque() == antes


def test_token_valido_preserva_comparacao_segura_e_fluxo_normal(cliente):
    token = "token-ascii-valido"
    with patch.object(
        sistema.secrets, "compare_digest", wraps=sistema.secrets.compare_digest
    ) as comparar:
        resposta = cliente.post(
            "/estoque/produtos",
            data={
                "csrf_token": token,
                "nome": "Shampoo",
                "unidade": "un",
                "estoque_minimo": "2",
            },
            follow_redirects=True,
        )
        assert resposta.status_code == 200
        comparar.assert_called_once_with(token, token)
    produto = listar_produtos()[0]["id_produto"]
    for tipo, quantidade in [("ENTRADA", 10), ("SAIDA", 3)]:
        resposta = cliente.post(
            "/estoque/movimentacoes",
            data={
                "csrf_token": token,
                "id_produto": str(produto),
                "tipo": tipo,
                "quantidade": str(quantidade),
            },
            follow_redirects=True,
        )
        assert resposta.status_code == 200
        assert "Movimentação registrada com sucesso." in resposta.get_data(as_text=True)
    assert listar_produtos()[0]["quantidade"] == 7
    assert [m["tipo"] for m in listar_movimentacoes()] == ["SAIDA", "ENTRADA"]


@pytest.mark.parametrize(
    "rota,campos,mensagem",
    [
        (
            "/estoque/produtos",
            {"estoque_minimo": str(MAX_SQLITE + 1)},
            "estoque mínimo",
        ),
        ("/estoque/movimentacoes", {"quantidade": str(MAX_SQLITE + 1)}, "quantidade"),
        (
            "/estoque/movimentacoes",
            {"tipo": "SAIDA", "quantidade": str(MAX_SQLITE + 1)},
            "quantidade",
        ),
        (
            "/estoque/movimentacoes",
            {"id_produto": str(MAX_SQLITE + 1)},
            "Produto inválido",
        ),
        (
            "/estoque/movimentacoes",
            {"tipo": "SAIDA", "id_produto": str(MAX_SQLITE + 1)},
            "Produto inválido",
        ),
    ],
)
def test_limites_pela_interface_exibem_mensagem_sem_alterar_dados(
    cliente, rota, campos, mensagem
):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    antes = estado_estoque()
    dados = {
        "csrf_token": "token-ascii-valido",
        "nome": "Novo",
        "unidade": "un",
        "estoque_minimo": "0",
        "id_produto": str(produto),
        "tipo": "ENTRADA",
        "quantidade": "1",
    }
    dados.update(campos)
    resposta = cliente.post(rota, data=dados, follow_redirects=True)
    assert resposta.status_code == 200
    assert mensagem in resposta.get_data(as_text=True)
    assert estado_estoque() == antes


def test_transbordamento_pela_interface_exibe_erro_e_preserva_historico(cliente):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", MAX_SQLITE)
    antes = estado_estoque()
    resposta = cliente.post(
        "/estoque/movimentacoes",
        data={
            "csrf_token": "token-ascii-valido",
            "id_produto": str(produto),
            "tipo": "ENTRADA",
            "quantidade": "1",
        },
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "limite máximo" in resposta.get_data(as_text=True)
    assert estado_estoque() == antes
