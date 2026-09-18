# Gerenciador de Projetos — API

API REST para gerenciamento de projetos e tarefas, desenvolvida para o desafio técnico de Desenvolvedor Python Pleno.

## Tecnologias

- Python 3.12
- FastAPI + Pydantic v2
- SQLAlchemy 2 + Alembic
- PostgreSQL
- JWT (python-jose) + bcrypt (passlib)
- Docker / Docker Compose
- Pytest + httpx (TestClient) + testcontainers-python

## Como executar

Pré-requisito: Docker e Docker Compose instalados.

1. Copie o arquivo de variáveis de ambiente de exemplo:

   ```bash
   cp .env.example .env
   ```

   Os valores padrão já funcionam para rodar localmente via Docker Compose. Ajuste `JWT_SECRET` para um valor próprio se desejar (não é obrigatório para rodar localmente).

2. Suba o ambiente completo:

   ```bash
   docker compose up --build
   ```

   Isso sobe dois serviços: `db` (PostgreSQL de desenvolvimento) e `api` (a aplicação FastAPI). O serviço `api` aguarda o `db` ficar saudável e **executa as migrations do Alembic automaticamente** antes de iniciar o servidor — nenhum passo manual adicional é necessário além do `.env`.

3. A documentação Swagger fica disponível em:

   ```
   http://localhost:8000/docs
   ```

## Como rodar os testes

Pré-requisitos: Docker rodando (Docker Desktop, ou equivalente) e as dependências Python instaladas num ambiente virtual local (`pip install -r requirements.txt`).

```bash
pytest -v
```

Não é necessário nenhum passo manual de infraestrutura antes — os testes usam [testcontainers-python](https://testcontainers-python.readthedocs.io/) para subir um container **Postgres efêmero, novo e isolado** automaticamente no início da sessão de testes (via `tests/conftest.py`), e derrubá-lo (incluindo o container "reaper" `testcontainers-ryuk`, que garante a limpeza mesmo se o processo travar) assim que a suíte terminar. Não existe mais um serviço `db_test` fixo no `docker-compose.yml`: o próprio `pytest` gerencia o ciclo de vida completo do banco de teste, container incluído.

Cada teste roda em uma execução isolada: as tabelas são recriadas e destruídas a cada função de teste (`setup_database` em `tests/conftest.py`), então a ordem de execução não importa e não há dados residuais entre testes.

## Estrutura do projeto

```text
app/
├── api/
│   ├── dependencies.py   # autenticação, sessão de DB, checagem de posse (owner)
│   └── routes/           # auth, projects, tasks
├── core/
│   ├── config.py         # Settings (pydantic-settings, lê do .env)
│   └── security.py       # hash de senha, criação/decodificação de JWT
├── models/                # SQLAlchemy (User, Project, Task)
├── repositories/          # consultas mais complexas (paginação/filtros de tasks)
├── schemas/                # Pydantic (validação de entrada/saída)
├── database.py            # engine, SessionLocal, Base
└── main.py                 # app FastAPI, routers, exception handlers

alembic/            # migrations
tests/               # pytest + conftest.py
```

## Decisões técnicas

- **HTTPBearer em vez de OAuth2PasswordBearer**: optei por `HTTPBearer` porque o `/auth/login` recebe as credenciais como JSON (não form-data), e o fluxo de autorização do desafio é apenas bearer token simples — não há necessidade do fluxo OAuth2 completo que o `OAuth2PasswordBearer` pressupõe (username/password via form). Depois evoluímos para uma `CustomHTTPBearer` que intercepta a exceção padrão do FastAPI e a converte para `401` com um `code` próprio (`MISSING_TOKEN`), distinguindo de um token presente porém inválido/expirado (`INVALID_TOKEN`) — ambos `401`, mas com mensagens diferentes para facilitar debug no cliente.
- **403 vs 404 para acesso negado**: ao acessar um projeto ou tarefa que não pertence ao usuário autenticado, a ordem de verificação é sempre a mesma: primeiro checamos se o recurso **existe** (senão, `404 PROJECT_NOT_FOUND`/`TASK_NOT_FOUND`); só depois, se existe, checamos se o usuário autenticado é o **dono** (senão, `403 PROJECT_ACCESS_DENIED`/`TASK_ACCESS_DENIED`). Isso significa que um usuário recebe `403` (não `404`) ao tentar acessar um recurso de outro usuário que existe de fato — uma escolha consciente de não esconder a existência do recurso atrás de um `404` genérico, já que o desafio pede explicitamente os dois códigos para cenários distintos (`403` para "sem permissão", `404` para "não existe").
- **Migrations automáticas no `docker compose up`**: o comando do serviço `api` no `docker-compose.yml` roda `alembic upgrade head` antes de iniciar o Uvicorn (`sh -c "alembic upgrade head && uvicorn ..."`). Sem isso, um `docker compose down -v && docker compose up --build` (ambiente do zero) subiria a API com o banco vazio, e qualquer rota que tocasse o banco quebraria com `500`. Rodar a migration como parte do boot do container garante que a aplicação nunca dependa de um passo manual (`docker compose run --rm api alembic upgrade head`) além da criação do `.env`, como exige o enunciado.
- **`compare_type=True` no Alembic, com limites**: habilitamos `compare_type=True` no `alembic/env.py` para que o autogenerate detecte trocas de tipo de coluna. Vale registrar uma limitação conhecida da biblioteca: mesmo com essa opção ativa, o Alembic **não** detecta mudanças de tamanho em colunas `VARCHAR` (ex.: `String(500)` para `String` sem limite) — só percebe mudanças de tipo/classe. Para esse tipo de alteração seria necessário um comparador de tipo customizado ou escrever a migration manualmente; como não havia necessidade real de remover o limite de 500 caracteres da descrição do projeto, optamos por manter `String(500)`, evitando essa complexidade.
- **Todos os models importados em `app/models/__init__.py`**: `Project.tasks` usa `relationship("Task", ...)` referenciando a classe pelo nome (string), técnica padrão do SQLAlchemy para evitar import circular entre `project.py` e `task.py`. Só que isso exige que a classe `Task` já tenha sido importada em algum lugar antes da primeira query rodar — senão o SQLAlchemy não consegue resolver o nome e a aplicação quebra com `500 Internal Server Error` em qualquer rota que toque `Project`, mesmo rotas aparentemente não relacionadas (ex.: `/auth/login`, que só usa `User`, mas dispara a configuração de todos os mappers). Resolvemos centralizando a importação de `User`, `Project` e `Task` em `app/models/__init__.py`, garantindo que os três sejam sempre registrados juntos assim que qualquer model for importado.
- **`order_by`/`direction` declarados como `Literal` na assinatura da rota, não só no schema**: a primeira versão da listagem de tasks recebia `order_by`/`direction` como `str` soltos via `Query`, e só validava o valor depois, ao instanciar `TaskFilterParams(...)` manualmente dentro do corpo da rota. O problema é que uma `ValidationError` do Pydantic levantada manualmente dentro do código da rota **não** é convertida automaticamente em `422` pelo FastAPI — isso só acontece para parâmetros validados na própria assinatura da função (via `Query`, `Depends`, corpo declarado, etc.). Um `order_by` inválido virava, então, um `500 Internal Server Error` não tratado. A correção foi declarar `order_by: Literal[...]` e `direction: Literal["asc", "desc"]` diretamente nos parâmetros da rota, deixando o FastAPI validar antes de qualquer construção manual de schema — garantindo o `422` esperado pelo enunciado para entradas inválidas.
- **Tratamento de erros centralizado em `app/main.py`**: além do formato consistente que já colocamos manualmente em cada `HTTPException` levantado nas rotas (`{"code": ..., "message": ...}`), adicionamos três handlers globais: um para `RequestValidationError` (padroniza todo `422` de validação, seja de body ou de query, incluindo os que o FastAPI gera automaticamente), um para `HTTPException`, e um catch-all para `Exception` (qualquer erro não tratado vira `500` padronizado, com o stack trace completo logado no servidor via `logger.exception`, sem vazar detalhes internos — como nome de tabela, coluna ou query SQL — na resposta ao cliente). Um detalhe que exigiu ajuste: o handler de `HTTPException` precisou ser registrado para `starlette.exceptions.HTTPException` (a classe-mãe), não `fastapi.exceptions.HTTPException` (a classe-filha que usamos manualmente nas rotas). Isso porque erros de roteamento interno do próprio framework — rota inexistente (`404`) e método não permitido (`405`) — são levantados pelo Starlette usando a classe-mãe diretamente; registrar o handler só na classe-filha deixava esses dois casos escaparem da padronização, sem o `code` no `detail`.
- **Sem regra de negócio própria que dispare `400` hoje**: o enunciado lista `400 Bad Request` como código esperado para "requisição inválida por regra de negócio". No estado atual do domínio (auth, projects, tasks), toda validação de entrada cai naturalmente em `422` (schema/Pydantic) e todo controle de acesso em `401`/`403`/`404`/`409`, sem nenhum caso que se encaixe especificamente como "regra de negócio violada" distinta de validação. Não implementamos um `400` artificial só para preencher a tabela; se uma regra desse tipo surgir (ex.: um limite de tarefas por projeto), o padrão de erro já está pronto para reutilizar (`HTTPException` com `detail={"code": ..., "message": ...}`).

## Diferenciais implementados

- **Refresh token com rotação e revogação**: `POST /auth/login` agora retorna `access_token` (JWT curto, `JWT_EXPIRE_MINUTES`, padrão 30 min) e `refresh_token` (string aleatória de alta entropia, `REFRESH_TOKEN_EXPIRE_DAYS`, padrão 7 dias). O refresh token nunca é guardado em texto puro no banco — só um hash SHA-256 dele (tabela `refresh_tokens`, coluna `token_hash`, `unique+index`). Diferente da senha (baixa entropia, precisa de bcrypt lento e salteado contra força bruta), um refresh token gerado com `secrets.token_urlsafe(32)` já tem 256 bits de entropia — SHA-256 simples é adequado e muito mais rápido, sem perda de segurança prática.
  - `POST /auth/refresh`: valida o refresh token recebido, emite um novo par `access_token`/`refresh_token`, e **revoga o token antigo** (`revoked_at`), registrando o novo como seu sucessor (`replaced_by_id`) — rotação a cada uso, nunca reaproveitando o mesmo refresh token duas vezes.
  - **Detecção de reuso**: se um refresh token já revogado/rotacionado for apresentado de novo (sinal de que foi vazado e um invasor está tentando usá-lo depois que o dono legítimo já rotacionou), a API revoga **todos** os refresh tokens ativos daquele usuário como contenção — forçando um novo login em todos os dispositivos, mesmo nos legítimos. É uma escolha deliberada de segurança sobre conveniência: preferimos deslogar o usuário legítimo a deixar uma sessão potencialmente comprometida ativa.
  - `POST /auth/logout`: revoga um refresh token específico sob demanda (encerra sessão daquele dispositivo/cliente).
  - Testado em `tests/test_auth.py`: emissão, rotação, detecção de reuso com revogação em cascata, e logout.
- **Paginação por cursor**: adicionamos `GET /projects/{project_id}/tasks/cursor` como um endpoint **adicional** à listagem paginada por `page`/`offset` já exigida pelo enunciado (não a substitui, já que o formato `{items, page, page_size, total, total_pages}` é um requisito obrigatório). O cursor é opaco ao cliente: um base64 de `created_at|id` do último item da página anterior (`app/core/cursor.py`). A consulta usa `WHERE (created_at, id) < (:cursor_created_at, :cursor_id) ORDER BY created_at DESC, id DESC LIMIT :limit + 1` — a composição `(created_at, id)` (não só `created_at`) evita ambiguidade em caso de empate de timestamp, e buscar `limit + 1` permite saber se existe próxima página (`has_more`) sem um segundo `COUNT` (que é justamente o que a paginação por cursor evita — por isso a resposta não tem `total`/`total_pages`, diferente da paginação por offset). Suporta os mesmos filtros (`status`, `priority`, `search`) da listagem paginada; não suporta `order_by` customizado, porque cursor pagination exige uma ordenação estável e determinística ligada à própria composição do cursor — permitir trocar a coluna de ordenação exigiria codificar qual coluna foi usada dentro do cursor, complexidade desnecessária para este diferencial. Testado em `tests/test_tasks.py`: cobertura completa de 12 itens sem sobreposição nem lacunas ao longo de 3 páginas, e cursor malformado retornando `422 INVALID_CURSOR`.
- **Testes de integração executados em containers**: `tests/conftest.py` usa [testcontainers-python](https://testcontainers-python.readthedocs.io/) (`PostgresContainer`) para subir um Postgres **real, efêmero e isolado** em container Docker automaticamente no início da sessão de testes, e derrubá-lo ao final (`_stop_postgres_container`, fixture de sessão) — inclusive o container "reaper" (`testcontainers-ryuk`) que garante a limpeza mesmo que o processo de teste seja interrompido abruptamente. Isso eliminou por completo o serviço `db_test` que existia antes no `docker-compose.yml`: não há mais nenhum passo manual de infraestrutura antes de rodar os testes — `pytest` sozinho já provisiona e descarta o banco. Confirmado na prática inspecionando `docker ps` durante uma execução de teste (um container `postgres:16` com nome aleatório aparece e desaparece junto com o Ryuk).

## Diferenciais não implementados

Os itens abaixo são listados como opcionais pelo enunciado e ainda não foram implementados nesta entrega. Descrição do que falta e de como seria feito:

- **Logs estruturados**: hoje só logamos exceções não tratadas via `logger.exception` (texto simples). Uma versão estruturada usaria algo como `structlog` ou `python-json-logger`, emitindo logs em JSON com `request_id`, `user_id`, rota e duração de cada requisição — mais fácil de agregar/consultar em ferramentas como ELK/Datadog.
- **Endpoint de healthcheck mais completo**: o `/health` atual só confirma que a aplicação está respondendo, sem checar a conexão com o banco. Uma versão mais completa faria um `SELECT 1` contra o Postgres e retornaria `503` se o banco estivesse inacessível.
- **Pipeline de CI**: não há GitHub Actions (ou similar) configurado para rodar `pytest` e lint automaticamente a cada push/PR. Seria um workflow simples: instalar dependências, garantir Docker disponível no runner (para o testcontainers) e rodar `pytest -v`, falhando o build se algum teste quebrar.
- **Lint e análise estática**: não configuramos `ruff`/`black`/`mypy`. Adicionaria `ruff` (lint + format, mais rápido que a combinação `flake8`+`black`) e `mypy` para checagem de tipos, ambos rodando como parte do CI.
- **Controle otimista de concorrência**: updates (`PUT`/`PATCH`) atuais não verificam se o registro foi alterado por outra requisição entre o `GET` e o `PUT`/`PATCH` do cliente (last-write-wins). Implementaria com uma coluna `version` (incrementada a cada update) ou comparação de `updated_at`, rejeitando a atualização com `409` se o valor enviado pelo cliente não bater com o atual no banco.
