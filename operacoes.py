
from contextlib import contextmanager
from datetime import date, datetime

from werkzeug.security import generate_password_hash
from database import conectar


@contextmanager
def abrir_banco():
    conexao = conectar()
    try:
        with conexao:
            yield conexao
    finally:
        conexao.close()


def cadastrar_usuario(nome, login, senha):
    if not nome.strip() or not login.strip():
        raise ValueError("Informe nome e login.")

    if len(senha) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")

    senha_hash = generate_password_hash(senha)

    with abrir_banco() as banco:
        resultado = banco.execute(
            """
            INSERT INTO usuario (nome, login, senha_hash)
            VALUES (?, ?, ?)
            """,
            (nome.strip(), login.strip(), senha_hash)
        )
        return resultado.lastrowid


def cadastrar_servico(nome, preco_centavos):
    if not nome.strip():
        raise ValueError("Informe o nome do serviço.")

    if type(preco_centavos) is not int or preco_centavos <= 0:
        raise ValueError("O preço deve ser positivo.")

    with abrir_banco() as banco:
        resultado = banco.execute(
            """
            INSERT INTO servico (nome, preco_padrao_centavos)
            VALUES (?, ?)
            """,
            (nome.strip(), preco_centavos)
        )
        return resultado.lastrowid


def registrar_atendimento(
    id_servico,
    id_usuario,
    status_pagamento,
    referencia_cliente=None
):
    if status_pagamento not in ("PAGO", "PENDENTE"):
        raise ValueError("Status de pagamento inválido.")

    referencia = (referencia_cliente or "").strip()

    if status_pagamento == "PENDENTE" and not referencia:
        raise ValueError(
            "Informe o nome ou apelido do cliente pendente."
        )

    agora = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    data_pagamento = (
        agora if status_pagamento == "PAGO" else None
    )

    with abrir_banco() as banco:
        servico = banco.execute(
            """
            SELECT preco_padrao_centavos
            FROM servico
            WHERE id_servico = ? AND ativo = 1
            """,
            (id_servico,)
        ).fetchone()

        if servico is None:
            raise ValueError("Serviço não encontrado ou inativo.")

        usuario = banco.execute(
            """
            SELECT id_usuario
            FROM usuario
            WHERE id_usuario = ? AND ativo = 1
            """,
            (id_usuario,)
        ).fetchone()

        if usuario is None:
            raise ValueError("Usuário não encontrado ou inativo.")

        resultado = banco.execute(
            """
            INSERT INTO atendimento (
                id_servico,
                id_usuario,
                data_atendimento,
                valor_cobrado_centavos,
                status_pagamento,
                data_pagamento,
                referencia_cliente
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id_servico,
                id_usuario,
                agora,
                servico["preco_padrao_centavos"],
                status_pagamento,
                data_pagamento,
                referencia or None
            )
        )

        return resultado.lastrowid


def confirmar_pagamento(id_atendimento):
    agora = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )

    with abrir_banco() as banco:
        resultado = banco.execute(
            """
            UPDATE atendimento
            SET status_pagamento = 'PAGO',
                data_pagamento = ?
            WHERE id_atendimento = ?
              AND status_pagamento = 'PENDENTE'
            """,
            (agora, id_atendimento)
        )

        if resultado.rowcount == 0:
            raise ValueError(
                "Atendimento não encontrado ou já pago."
            )


def resumo_diario(data_consulta=None):
    dia = data_consulta or date.today().isoformat()

    with abrir_banco() as banco:
        atendimentos = banco.execute(
            """
            SELECT COUNT(*) AS total
            FROM atendimento
            WHERE substr(data_atendimento, 1, 10) = ?
            """,
            (dia,)
        ).fetchone()["total"]

        recebido = banco.execute(
            """
            SELECT COALESCE(
                SUM(valor_cobrado_centavos), 0
            ) AS total
            FROM atendimento
            WHERE status_pagamento = 'PAGO'
              AND substr(data_pagamento, 1, 10) = ?
            """,
            (dia,)
        ).fetchone()["total"]

        pendente = banco.execute(
            """
            SELECT COALESCE(
                SUM(valor_cobrado_centavos), 0
            ) AS total
            FROM atendimento
            WHERE status_pagamento = 'PENDENTE'
            """
        ).fetchone()["total"]

    return {
        "atendimentos_dia": atendimentos,
        "recebido_centavos": recebido,
        "pendente_total_centavos": pendente
    }
