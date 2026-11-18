from contextlib import closing

import pytest

import database
from estoque import (
    cadastrar_produto,
    listar_movimentacoes,
    listar_produtos,
    movimentar_estoque,
)
from operacoes import (
    cadastrar_servico,
    cadastrar_usuario,
    confirmar_pagamento,
    registrar_atendimento,
    resumo_diario,
)


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "BANCO", tmp_path / "validacoes.db")
    database.criar_tabelas()


def estado_estoque():
    with closing(database.conectar()) as banco:
        return tuple(
            [tuple(linha) for linha in banco.execute(consulta)]
            for consulta in (
                "SELECT * FROM produto ORDER BY id_produto",
                "SELECT * FROM movimentacao_estoque ORDER BY id_movimentacao",
            )
        )


def estado_financeiro():
    with closing(database.conectar()) as banco:
        return tuple(
            [tuple(linha) for linha in banco.execute(consulta)]
            for consulta in (
                "SELECT * FROM usuario ORDER BY id_usuario",
                "SELECT * FROM servico ORDER BY id_servico",
                "SELECT * FROM atendimento ORDER BY id_atendimento",
            )
        )


def test_cadastro_persiste_campos_e_inicia_sem_movimentacao():
    identificador = cadastrar_produto("  Shampoo  ", "  ml  ", 2)
    produto = dict(listar_produtos()[0])
    assert produto == {
        "id_produto": identificador,
        "nome": "Shampoo",
        "unidade": "ml",
        "quantidade": 0,
        "estoque_minimo": 2,
    }
    assert listar_movimentacoes() == []


def test_cadastro_com_limites_permitidos_e_valores_padrao():
    cadastrar_produto("N" * 100, "u" * 15, 0)
    cadastrar_produto("Pente")
    produtos = {p["nome"]: p for p in listar_produtos()}
    assert produtos["N" * 100]["unidade"] == "u" * 15
    assert produtos["Pente"]["unidade"] == "un"
    assert produtos["Pente"]["estoque_minimo"] == 0


@pytest.mark.parametrize(
    "campos",
    [
        {"nome": ""},
        {"nome": "   "},
        {"nome": None},
        {"nome": "N" * 101},
        {"unidade": ""},
        {"unidade": "   "},
        {"unidade": None},
        {"unidade": "u" * 16},
        {"estoque_minimo": -1},
        {"estoque_minimo": True},
        {"estoque_minimo": 1.5},
        {"estoque_minimo": "2"},
    ],
)
def test_cadastro_invalido_preserva_dados_anteriores(campos):
    existente = cadastrar_produto("Existente")
    movimentar_estoque(existente, "ENTRADA", 5)
    antes = estado_estoque()
    argumentos = {"nome": "Novo", "unidade": "un", "estoque_minimo": 0}
    argumentos.update(campos)
    with pytest.raises(ValueError):
        cadastrar_produto(**argumentos)
    assert estado_estoque() == antes


@pytest.mark.parametrize("nome", ["Shampoo", "shampoo", "  SHAMPOO  "])
def test_cadastro_duplicado_preserva_produto_e_historico(nome):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 5)
    antes = estado_estoque()
    with pytest.raises(ValueError, match="Já existe um produto"):
        cadastrar_produto(nome)
    assert estado_estoque() == antes


@pytest.mark.parametrize("tipo", ["ENTRADA", "SAIDA"])
@pytest.mark.parametrize(
    "campo,valor",
    [
        ("quantidade", 0),
        ("quantidade", -1),
        ("quantidade", True),
        ("quantidade", 1.5),
        ("quantidade", "1"),
        ("id_produto", 0),
        ("id_produto", -1),
        ("id_produto", True),
        ("id_produto", "1"),
        ("observacao", "x" * 201),
    ],
)
def test_movimentacao_invalida_preserva_saldo_e_historico(tipo, campo, valor):
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 7)
    antes = estado_estoque()
    argumentos = {"id_produto": produto, "tipo": tipo, "quantidade": 1}
    argumentos[campo] = valor
    with pytest.raises(ValueError):
        movimentar_estoque(**argumentos)
    assert estado_estoque() == antes


def test_saida_superior_ao_saldo_informa_erro_e_preserva_registros():
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 10, "Compra")
    movimentar_estoque(produto, "SAIDA", 3, "Uso")
    antes = estado_estoque()
    with pytest.raises(ValueError, match="Estoque insuficiente para a saída"):
        movimentar_estoque(produto, "SAIDA", 8)
    assert estado_estoque() == antes
    assert listar_produtos()[0]["quantidade"] == 7
    assert len(listar_movimentacoes()) == 2


def test_estoque_preserva_financeiro_e_pagamento_preserva_estoque():
    usuario = cadastrar_usuario("Barbeiro", "barbeiro", "SenhaTeste123!")
    servico = cadastrar_servico("Corte", 2500)
    pago = registrar_atendimento(servico, usuario, "PAGO")
    pendente = registrar_atendimento(servico, usuario, "PENDENTE", "Cliente")
    # Simula registros preexistentes de uma data anterior.
    with closing(database.conectar()) as banco:  # noqa: SIM117
        with banco:
            banco.execute(
                """UPDATE atendimento SET data_atendimento = ?,
                   data_pagamento = CASE WHEN status_pagamento = 'PAGO' THEN ? ELSE NULL END
                   WHERE id_atendimento IN (?, ?)""",
                (
                    "2025-01-10T10:00:00-03:00",
                    "2025-01-10T10:00:00-03:00",
                    pago,
                    pendente,
                ),
            )
    financeiro_antes = estado_financeiro()
    resumo_antes = resumo_diario("2025-01-10")
    produto = cadastrar_produto("Shampoo")
    movimentar_estoque(produto, "ENTRADA", 10)
    movimentar_estoque(produto, "SAIDA", 3)
    listar_movimentacoes()
    with pytest.raises(ValueError, match="Estoque insuficiente"):
        movimentar_estoque(produto, "SAIDA", 8)
    assert estado_financeiro() == financeiro_antes
    assert (
        resumo_diario("2025-01-10")
        == resumo_antes
        == {
            "atendimentos_dia": 2,
            "recebido_centavos": 2500,
            "pendente_total_centavos": 2500,
        }
    )
    estoque_antes = estado_estoque()
    confirmar_pagamento(pendente)
    assert resumo_diario()["pendente_total_centavos"] == 0
    with closing(database.conectar()) as banco:
        registro = banco.execute(
            "SELECT status_pagamento, data_pagamento FROM atendimento WHERE id_atendimento = ?",
            (pendente,),
        ).fetchone()
    assert registro["status_pagamento"] == "PAGO"
    assert registro["data_pagamento"] is not None
    with pytest.raises(ValueError, match="já pago"):
        confirmar_pagamento(pendente)
    assert estado_estoque() == estoque_antes
