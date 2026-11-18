
import sqlite3
from contextlib import closing
from decimal import Decimal, InvalidOperation
from getpass import getpass

from database import conectar, criar_tabelas
from operacoes import cadastrar_servico, cadastrar_usuario


def informar_preco():
    while True:
        texto = input("Preço em reais (ex.: 30,00): ")
        texto = texto.strip().replace(",", ".")

        try:
            valor = Decimal(texto)
            centavos = valor * 100

            if (
                not centavos.is_finite()
                or centavos <= 0
                or centavos != centavos.to_integral_value()
            ):
                raise ValueError

            return int(centavos)

        except (InvalidOperation, ValueError):
            print("Informe um preço válido, como 30,00.")


def configurar():
    criar_tabelas()

    with closing(conectar()) as banco:
        usuarios = banco.execute(
            "SELECT COUNT(*) FROM usuario"
        ).fetchone()[0]

    if usuarios == 0:
        print("\n=== CRIAR PRIMEIRO USUÁRIO ===")

        while True:
            nome = input("Nome do responsável: ").strip()
            login = input("Nome de usuário: ").strip()
            senha = getpass("Crie uma senha: ")
            confirmacao = getpass("Confirme a senha: ")

            if senha != confirmacao:
                print("As senhas não coincidem.")
                continue

            try:
                cadastrar_usuario(nome, login, senha)
                print("Usuário criado com sucesso!")
                break

            except ValueError as erro:
                print(erro)
    else:
        print("Já existe um usuário cadastrado.")

    print("\n=== CADASTRAR SERVIÇOS ===")
    print("Deixe o nome vazio para terminar.")

    while True:
        nome = input("\nNome do serviço: ").strip()

        if not nome:
            break

        preco = informar_preco()

        try:
            cadastrar_servico(nome, preco)
            print("Serviço cadastrado com sucesso!")

        except (ValueError, sqlite3.IntegrityError) as erro:
            print("Não foi possível cadastrar:", erro)

    print("\nConfiguração concluída!")


if __name__ == "__main__":
    configurar()
