import sqlite3
from datetime import datetime

from operacoes import abrir_banco


def cadastrar_produto(nome, unidade="un", estoque_minimo=0):
    nome = (nome or "").strip()
    unidade = (unidade or "").strip()

    if not nome or len(nome) > 100:
        raise ValueError("Informe um nome com até 100 caracteres.")

    if not unidade or len(unidade) > 15:
        raise ValueError("Informe uma unidade válida.")

    if type(estoque_minimo) is not int or estoque_minimo < 0:
        raise ValueError("O estoque mínimo deve ser zero ou maior.")

    try:
        with abrir_banco() as banco:
            resultado = banco.execute(
                """
                INSERT INTO produto (nome, unidade, estoque_minimo)
                VALUES (?, ?, ?)
                """,
                (nome, unidade, estoque_minimo),
            )
            return resultado.lastrowid

    except sqlite3.IntegrityError:
        raise ValueError("Já existe um produto com esse nome.") from None


def listar_produtos():
    with abrir_banco() as banco:
        return banco.execute(
            """
            SELECT
                id_produto,
                nome,
                unidade,
                quantidade,
                estoque_minimo
            FROM produto
            WHERE ativo = 1
            ORDER BY nome
            """
        ).fetchall()


def listar_movimentacoes():
    """Consulta o histórico, incluindo produtos que foram desativados."""
    with abrir_banco() as banco:
        return banco.execute(
            """
            SELECT
                m.id_movimentacao,
                m.id_produto,
                p.nome,
                p.unidade,
                m.tipo,
                m.quantidade,
                m.data_movimentacao,
                m.observacao
            FROM movimentacao_estoque AS m
            JOIN produto AS p ON p.id_produto = m.id_produto
            ORDER BY julianday(m.data_movimentacao) DESC,
                     m.id_movimentacao DESC
            """
        ).fetchall()


def movimentar_estoque(id_produto, tipo, quantidade, observacao=""):
    if type(id_produto) is not int or id_produto <= 0:
        raise ValueError("Produto inválido.")

    if tipo not in ("ENTRADA", "SAIDA"):
        raise ValueError("Tipo de movimentação inválido.")

    if type(quantidade) is not int or quantidade <= 0:
        raise ValueError("A quantidade deve ser positiva.")

    observacao = (observacao or "").strip()

    if len(observacao) > 200:
        raise ValueError("Observação muito longa.")

    agora = datetime.now().astimezone().isoformat(timespec="seconds")

    with abrir_banco() as banco:
        produto = banco.execute(
            """
            SELECT id_produto
            FROM produto
            WHERE id_produto = ? AND ativo = 1
            """,
            (id_produto,),
        ).fetchone()

        if produto is None:
            raise ValueError("Produto não encontrado.")

        if tipo == "ENTRADA":
            banco.execute(
                """
                UPDATE produto
                SET quantidade = quantidade + ?
                WHERE id_produto = ?
                """,
                (quantidade, id_produto),
            )
        else:
            resultado = banco.execute(
                """
                UPDATE produto
                SET quantidade = quantidade - ?
                WHERE id_produto = ?
                  AND quantidade >= ?
                """,
                (quantidade, id_produto, quantidade),
            )

            if resultado.rowcount != 1:
                raise ValueError("Estoque insuficiente para a saída.")

        banco.execute(
            """
            INSERT INTO movimentacao_estoque (
                id_produto,
                tipo,
                quantidade,
                data_movimentacao,
                observacao
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (id_produto, tipo, quantidade, agora, observacao or None),
        )
