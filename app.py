
from flask import Flask
from database import criar_tabelas

app = Flask(__name__)

# Prepara as tabelas do banco SQLite
criar_tabelas()


@app.route("/")
def inicio():
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1">
        <title>Barbearia Chita do Corte</title>
    </head>
    <body>
        <h1>Barbearia Chita do Corte</h1>
        <p>Sistema de controle de atendimentos e pagamentos.</p>
    </body>
    </html>
    """


if __name__ == "__main__":
    app.run(debug=False)
