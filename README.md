
# Barbearia Chita do Corte

Sistema web desenvolvido para organizar os atendimentos
e os pagamentos da Barbearia Chita do Corte.

## Funcionalidades

- Registro de atendimentos realizados.
- Controle de pagamentos recebidos e pendentes.
- Resumo de atendimentos e valores do dia.
- Autenticação de usuário.
- Interface responsiva.

## Tecnologias

- Python
- Flask
- SQLite
- HTML5, CSS3 e JavaScript
- Pytest

## Como executar

Instale as dependências:

```powershell
py -m pip install -r requirements.txt
```

Configure o primeiro usuário e os serviços:

```powershell
py configurar.py
```

Inicie o sistema:

```powershell
py app.py
```

Acesse http://127.0.0.1:5000 no navegador.

## Testes

Execute os testes automatizados:

```powershell
py -m pytest -q
```

Os testes também são executados pelo GitHub Actions.

## Objetivo

Apoiar o controle financeiro e operacional
de uma pequena barbearia, com foco na
simplicidade de utilização.

