# Gerenciador de Projetos — API

API REST para gerenciamento de projetos e tarefas, desenvolvida para o desafio técnico de Desenvolvedor Python Pleno.

## Tecnologias

- Python 3.12
- FastAPI + Pydantic v2
- SQLAlchemy 2 + Alembic
- PostgreSQL
- JWT (python-jose) + bcrypt (passlib)
- structlog (logs estruturados em JSON)
- Docker / Docker Compose
- Pytest + httpx (TestClient) + testcontainers-python
- ruff + mypy (lint, formatação e checagem de tipos)
- GitHub Actions (CI)

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

   Sobe dois serviços: `db` (Postgres) e `api` (FastAPI). A `api` aguarda o `db` ficar saudável e **executa as migrations automaticamente** antes de iniciar — nenhum passo manual além do `.env`.

3. A documentação Swagger fica disponível em:

   ```
   http://localhost:8000/docs
   ```

## Como rodar os testes

Pré-requisitos: Docker rodando (Docker Desktop, ou equivalente) e as dependências Python instaladas num ambiente virtual local (`pip install -r requirements.txt`).

```bash
pytest -v
```

Os testes usam [testcontainers-python](https://testcontainers-python.readthedocs.io/) para subir um Postgres efêmero automaticamente (via `tests/conftest.py`) e derrubá-lo ao final — nenhum passo manual de infraestrutura antes, sem serviço `db_test` fixo no compose. Cada teste recria e destrói as tabelas (`setup_database`), então a ordem não importa e não há dados residuais entre execuções.

## Lint e checagem de tipos

```bash
ruff check .
ruff format --check .
mypy app tests
```

Roda automaticamente no CI a cada push/PR (job `lint`). `ruff format .` (sem `--check`) aplica a formatação automaticamente.

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

- **HTTPBearer em vez de OAuth2PasswordBearer**: login recebe JSON, não form-data, então o fluxo OAuth2 completo não se aplica. Uma `CustomHTTPBearer` distingue token ausente (`401 MISSING_TOKEN`) de token inválido/expirado (`401 INVALID_TOKEN`).
- **403 só depois de checar que o recurso existe**: acesso a um projeto/tarefa de outro usuário sempre checa existência primeiro (`404` se não existe) e posse depois (`403` se existe mas não é do dono) — nunca esconde a existência de um recurso atrás de um `404` genérico.
- **Migrations automáticas no boot do container** *(bug real corrigido)*: sem isso, `docker compose up --build` num ambiente do zero subia a API com o banco vazio e qualquer rota quebrava com `500`. Corrigido rodando `alembic upgrade head` no `command` do serviço `api`, antes do Uvicorn.
- **Limite conhecido do Alembic**: mesmo com `compare_type=True`, o autogenerate não detecta mudança de *tamanho* em `VARCHAR` (só de tipo) — por isso mantivemos `String(500)` como está, em vez de brigar com a ferramenta por uma mudança sem necessidade real.
- **Models centralizados em `app/models/__init__.py`** *(bug real corrigido)*: `relationship("Task", ...)` referencia a classe por string para evitar import circular, mas isso quebra com `500` se `Task` nunca foi importada antes da primeira query. Resolvido importando `User`, `Project` e `Task` juntos num só lugar.
- **`order_by`/`direction` como `Literal` na rota, não só no schema** *(bug real corrigido)*: validar manualmente dentro do corpo da rota não gera `422` automático do FastAPI — só parâmetros validados na própria assinatura (via `Query`) geram. Um valor inválido virava `500` até declarar `Literal[...]` direto no parâmetro.
- **Handler de erro na classe-mãe do Starlette** *(bug real corrigido)*: `404`/`405` internos do framework usam `starlette.exceptions.HTTPException`, não a subclasse do FastAPI usada nas rotas — registrar o handler só na subclasse deixava esses dois casos fora do formato `{"code", "message"}` padronizado.
- **Sem `400` próprio**: toda validação de entrada cai naturalmente em `422` (Pydantic) e todo controle de acesso em `401`/`403`/`404`/`409`; não criamos um caso artificial só para preencher esse código.

## Diferenciais implementados

Todos os 8 diferenciais opcionais listados no enunciado foram implementados:

- **Refresh token com rotação e revogação**: `POST /auth/login` retorna `access_token` (JWT curto) e `refresh_token` (string aleatória, guardada como hash SHA-256 — não bcrypt, porque já nasce com alta entropia). `POST /auth/refresh` rotaciona a cada uso (revoga o antigo, emite um novo par); reapresentar um token já revogado revoga **todos** os tokens ativos do usuário, como contenção contra um token vazado. `POST /auth/logout` revoga sob demanda. Testado em `tests/test_auth.py`.
- **Paginação por cursor**: `GET /projects/{id}/tasks/cursor`, adicional à paginação por `page`/`offset` (que continua obrigatória, com seu formato de resposta fixo). Cursor opaco em base64 (`created_at|id`); busca `limit + 1` registros para saber `has_more` sem um `COUNT` extra. Testado com 12 itens em 3 páginas sem sobreposição/lacuna, e cursor inválido retornando `422`.
- **Testes de integração em containers**: `tests/conftest.py` usa [testcontainers-python](https://testcontainers-python.readthedocs.io/) para subir/derrubar um Postgres efêmero real a cada sessão de testes — `pytest -v` sozinho já provisiona tudo, sem exigir nenhum serviço de banco de pé antes.
- **Logs estruturados**: [structlog](https://www.structlog.org/) (`app/core/logging.py`) emite cada requisição como uma linha JSON (`request_id`, `user_id`, `status_code`, `duration_ms`...), com o `request_id` também devolvido no header `X-Request-ID`. Detalhe não óbvio: o `BaseHTTPMiddleware` do Starlette roda a rota numa *task* asyncio separada da própria middleware, então `user_id` precisou ser passado via `request.state` (não só `contextvars`) para chegar no log final da requisição.
- **Healthcheck verificando o banco**: `GET /health` roda um `SELECT 1` real a cada chamada — `200` se o banco responde, `503` se não. Testado derrubando o `db` de verdade (`docker compose stop db`) e confirmando o `503`.
- **Pipeline de CI**: `.github/workflows/ci.yml`, três jobs em paralelo — `test` (pytest; sem serviço `postgres` no workflow, já que o testcontainers cuida disso sozinho), `lint` (ruff + mypy) e `docker-build` (garante que o `Dockerfile` continua buildando).
- **Lint e análise estática**: `ruff` (lint + format) e `mypy`, configurados em `pyproject.toml` e rodando no CI. `B008` ignorado (é o padrão do `Depends()` do FastAPI, não um bug real); `alembic/` excluído (código gerado). Corrigiu achados reais: `raise ... from None` faltando em alguns `except`, enums migrados para `enum.StrEnum`, forward references de relacionamento protegidas com `TYPE_CHECKING`.
- **Controle otimista de concorrência**: `Project`/`Task` ganharam uma coluna `version`. `PUT`/`PATCH` exigem essa versão no payload (a que o cliente viu no último `GET`) — se não bater com a do banco, `409 VERSION_CONFLICT` sem aplicar a mudança; se bater, aplica e incrementa. Evita que uma atualização sobrescreva outra silenciosamente (*last-write-wins*). Testado com update bem-sucedido (incrementa versão) e update com versão desatualizada (`409`).
