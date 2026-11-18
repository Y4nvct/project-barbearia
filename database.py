import sqlite3
from pathlib import Path

BANCO = Path(__file__).with_name("barbearia.db")


def conectar():
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_tabelas():
    conexao = conectar()

    try:
        conexao.executescript("""
            CREATE TABLE IF NOT EXISTS usuario (
                id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                login TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                ativo INTEGER NOT NULL DEFAULT 1
                    CHECK (ativo IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS servico (
                id_servico INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                preco_padrao_centavos INTEGER NOT NULL
                    CHECK (preco_padrao_centavos > 0),
                ativo INTEGER NOT NULL DEFAULT 1
                    CHECK (ativo IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS atendimento (
                id_atendimento INTEGER PRIMARY KEY AUTOINCREMENT,
                id_servico INTEGER NOT NULL,
                id_usuario INTEGER NOT NULL,
                data_atendimento TEXT NOT NULL,
                valor_cobrado_centavos INTEGER NOT NULL
                    CHECK (valor_cobrado_centavos > 0),
                status_pagamento TEXT NOT NULL
                    CHECK (status_pagamento IN ('PAGO', 'PENDENTE')),
                data_pagamento TEXT,
                referencia_cliente TEXT,

                FOREIGN KEY (id_servico)
                    REFERENCES servico(id_servico),
                FOREIGN KEY (id_usuario)
                    REFERENCES usuario(id_usuario),

                CHECK (
                    (status_pagamento = 'PAGO'
                        AND data_pagamento IS NOT NULL)
                    OR
                    (status_pagamento = 'PENDENTE'
                        AND data_pagamento IS NULL)
                )
            );


            CREATE TABLE IF NOT EXISTS produto (
                id_produto INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL COLLATE NOCASE UNIQUE,
                unidade TEXT NOT NULL DEFAULT 'un',
                quantidade INTEGER NOT NULL DEFAULT 0
                    CHECK (quantidade >= 0),
                estoque_minimo INTEGER NOT NULL DEFAULT 0
                    CHECK (estoque_minimo >= 0),
                ativo INTEGER NOT NULL DEFAULT 1
                    CHECK (ativo IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS movimentacao_estoque (
                id_movimentacao INTEGER PRIMARY KEY AUTOINCREMENT,
                id_produto INTEGER NOT NULL,
                tipo TEXT NOT NULL
                    CHECK (tipo IN ('ENTRADA', 'SAIDA')),
                quantidade INTEGER NOT NULL
                    CHECK (quantidade > 0),
                data_movimentacao TEXT NOT NULL,
                observacao TEXT,
                FOREIGN KEY (id_produto)
                    REFERENCES produto(id_produto)
            );

            CREATE INDEX IF NOT EXISTS idx_movimentacao_estoque_produto
                ON movimentacao_estoque(id_produto, data_movimentacao);


            CREATE INDEX IF NOT EXISTS idx_atendimento_data
                ON atendimento(data_atendimento);

            CREATE INDEX IF NOT EXISTS idx_atendimento_status
                ON atendimento(status_pagamento);

            CREATE INDEX IF NOT EXISTS idx_pagamento_data
                ON atendimento(data_pagamento);
        """)

        conexao.commit()

    finally:
        conexao.close()


if __name__ == "__main__":
    criar_tabelas()
    print("Banco de dados preparado com sucesso!")
