# Barbearia Chita do Corte

MVP web para organizar atendimentos, pagamentos e materiais utilizados na barbearia.

## Funcionalidades

- Login com senhas armazenadas como hash, saída da sessão e proteção de formulários por CSRF.
- Registro de atendimentos pagos ou pendentes, com identificação do cliente nas pendências.
- Confirmação de pagamentos, resumo financeiro diário e total de pendências em aberto.
- Calendário para consultar uma data e compará-la com o dia anterior.
- Interface responsiva, modo escuro, alto contraste, controles com rótulos acessíveis e indicação de foco.
- Cadastro de produtos com unidade de medida, saldo e estoque mínimo.
- Entradas e saídas de materiais com observação opcional e bloqueio de saída superior ao saldo.
- Histórico de movimentações, incluindo produtos inativos, ordenado da mais recente para a mais antiga.
- Atualização do saldo e gravação do histórico na mesma transação: em caso de falha, ambas são desfeitas.

O resumo de valores recebidos usa a data do pagamento. As pendências em aberto são gerais, independentemente da data consultada. O nome ou apelido do cliente aceita até 100 caracteres.

## Tecnologias

- Python 3.12 (versão utilizada no GitHub Actions).
- Flask e Werkzeug para aplicação web, sessões e senhas.
- SQLite, por meio do módulo `sqlite3` do Python.
- HTML5, CSS3 e JavaScript.
- Pytest para testes; GitHub Actions e pytest-cov para automação e cobertura.

## Instalação e execução

No PowerShell, dentro da pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Em uma instalação nova, configure o primeiro usuário e os serviços:

```powershell
.\.venv\Scripts\python.exe configurar.py
```

A configuração solicita nome, login, senha e serviços. O arquivo local `barbearia.db` é criado quando necessário. Em uma instalação existente, preserve esse arquivo; não é necessário apagá-lo ou recriá-lo para executar o sistema.

Opcionalmente, configure a variável de ambiente `SECRET_KEY` com uma chave aleatória persistente antes de iniciar o sistema. Sem ela, uma chave é gerada a cada inicialização e as sessões anteriores deixam de ser válidas. A aplicação não carrega arquivos `.env` automaticamente.

Inicie a aplicação:

```powershell
.\.venv\Scripts\python.exe app.py
```

Acesse [http://127.0.0.1:5000](http://127.0.0.1:5000). O servidor iniciado dessa forma é destinado à execução local do MVP.

## Testes

Execute a suíte na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes redirecionam `database.BANCO` para arquivos em diretórios temporários antes de criar tabelas ou gravar dados. Não utilizam o banco real da barbearia.

- `tests/test_operacoes.py`: usuários, serviços, atendimentos, pagamentos e limite do nome do cliente.
- `tests/test_integracao.py`: autenticação, formulários, CSRF, configuração inicial e calendário financeiro.
- `tests/test_estoque.py`: histórico, entradas, saídas, ordenação, persistência e reversão de transações.
- `tests/test_validacoes_estoque.py`: 39 casos adicionais de cadastro, validações e preservação entre estoque e financeiro.

O GitHub Actions executa os testes e mede a cobertura em pushes, pull requests e acionamento manual. Para reproduzir a medição localmente:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest-cov
.\.venv\Scripts\python.exe -m coverage run --source=. --omit="*/tests/*,*/.venv/*" -m pytest -q
.\.venv\Scripts\python.exe -m coverage report -m
```

## Dados locais

O banco `barbearia.db` e seus arquivos auxiliares são ignorados pelo Git, assim como o ambiente virtual e os caches. Não publique bancos, backups, credenciais ou arquivos de configuração contendo segredos. As alterações de código não devem substituir os dados da instalação existente.
