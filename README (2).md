# Desafio Técnico — Desenvolvedor Python Pleno

## Objetivo

Desenvolver uma API REST para gerenciamento de projetos e tarefas. A aplicação deverá permitir o cadastro e a autenticação de usuários, além de controlar o acesso aos dados de cada usuário.

O desafio avaliará conhecimentos em Python, FastAPI, Pydantic, PostgreSQL, autenticação com JWT, paginação, Docker, testes e organização de código.

## Tecnologias obrigatórias

- Python 3.12 ou superior
- FastAPI
- Pydantic v2
- PostgreSQL
- SQLAlchemy 2
- JWT
- Alembic
- Docker
- Docker Compose

## Requisitos funcionais

### 1. Usuários e autenticação

Cada usuário deverá possuir os seguintes campos:

| Campo | Tipo | Observação |
| --- | --- | --- |
| `id` | UUID | Chave primária |
| `name` | string | Nome do usuário |
| `email` | string | Deve ser único |
| `password_hash` | string | Senha armazenada de forma segura |
| `created_at` | datetime | Data de criação |

Endpoints obrigatórios:

```http
POST /auth/register
POST /auth/login
GET  /auth/me
```

O login deverá retornar um token JWT:

```json
{
  "access_token": "token-jwt",
  "token_type": "bearer"
}
```

Regras:

- A senha nunca deverá ser armazenada ou retornada em texto puro.
- O e-mail deverá ser validado.
- O token JWT deverá possuir tempo de expiração.
- O endpoint `/auth/me` deverá exigir autenticação.

### 2. Projetos

Cada projeto deverá possuir:

| Campo | Tipo | Observação |
| --- | --- | --- |
| `id` | UUID | Chave primária |
| `name` | string | Nome do projeto |
| `description` | string ou nulo | Descrição opcional |
| `owner_id` | UUID | Usuário proprietário |
| `created_at` | datetime | Data de criação |
| `updated_at` | datetime | Data da última alteração |

Endpoints obrigatórios:

```http
POST   /projects
GET    /projects
GET    /projects/{project_id}
PUT    /projects/{project_id}
DELETE /projects/{project_id}
```

Regras:

- Todas as rotas deverão exigir autenticação.
- O usuário poderá visualizar, alterar ou excluir somente os próprios projetos.
- A exclusão de um projeto deverá excluir suas tarefas.
- O nome do projeto deverá possuir entre 3 e 100 caracteres.

### 3. Tarefas

Cada tarefa deverá possuir:

| Campo | Tipo | Observação |
| --- | --- | --- |
| `id` | UUID | Chave primária |
| `title` | string | Título da tarefa |
| `description` | string ou nulo | Descrição opcional |
| `status` | enum | Situação atual |
| `priority` | enum | Prioridade |
| `due_date` | datetime ou nulo | Prazo opcional |
| `project_id` | UUID | Projeto relacionado |
| `created_at` | datetime | Data de criação |
| `updated_at` | datetime | Data da última alteração |

Valores permitidos para `status`:

```text
pending
in_progress
completed
```

Valores permitidos para `priority`:

```text
low
medium
high
```

Endpoints obrigatórios:

```http
POST   /projects/{project_id}/tasks
GET    /projects/{project_id}/tasks
GET    /tasks/{task_id}
PATCH  /tasks/{task_id}
DELETE /tasks/{task_id}
```

Regras:

- O usuário somente poderá acessar tarefas pertencentes aos próprios projetos.
- O título deverá possuir entre 3 e 120 caracteres.
- `due_date` não poderá ser uma data passada no momento do cadastro.
- `status` e `priority` deverão ser implementados com enums.
- O endpoint `PATCH` deverá aceitar atualizações parciais.

## Paginação, filtros e ordenação

Os endpoints de listagem deverão possuir paginação:

```http
GET /projects?page=1&page_size=20
GET /projects/{project_id}/tasks?page=1&page_size=20
```

Formato esperado da resposta:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

Regras da paginação:

- `page` deverá começar em `1`.
- `page_size` deverá aceitar valores entre `1` e `100`.
- A paginação deverá ser executada na consulta ao PostgreSQL, e não sobre dados já carregados em memória.
- O total de registros deverá considerar os filtros aplicados.

A listagem de tarefas também deverá aceitar filtros, busca e ordenação:

```http
GET /projects/{project_id}/tasks?status=pending
GET /projects/{project_id}/tasks?priority=high
GET /projects/{project_id}/tasks?search=relatorio
GET /projects/{project_id}/tasks?order_by=created_at&direction=desc
```

Os parâmetros poderão ser combinados:

```http
GET /projects/{project_id}/tasks?status=pending&priority=high&page=1&page_size=10
```

## Validação dos dados

Utilize schemas Pydantic separados para criação, atualização e resposta.

Exemplo:

```python
from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str | None = None
    priority: TaskPriority
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
```

Também deverá existir um schema genérico ou reutilizável para respostas paginadas.

## Tratamento de erros

A API deverá retornar códigos HTTP coerentes, incluindo:

| Código | Situação esperada |
| --- | --- |
| `400 Bad Request` | Requisição inválida por regra de negócio |
| `401 Unauthorized` | Token ausente, inválido ou expirado |
| `403 Forbidden` | Tentativa de acesso a recurso sem permissão |
| `404 Not Found` | Recurso não encontrado |
| `409 Conflict` | Conflito, como e-mail já cadastrado |
| `422 Unprocessable Entity` | Falha de validação dos dados |

As respostas de erro deverão seguir um formato consistente. Exemplo:

```json
{
  "detail": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Projeto não encontrado"
  }
}
```

## Banco de dados e migrations

- Utilize PostgreSQL como banco de dados.
- Crie os relacionamentos e constraints necessários.
- Utilize migrations com Alembic.
- Não utilize criação automática das tabelas como substituição das migrations.
- Inclua no repositório todas as migrations necessárias para iniciar o projeto.

## Docker

O ambiente completo deverá ser iniciado com:

```bash
docker compose up --build
```

O arquivo `docker-compose.yml` deverá possuir, no mínimo:

- Serviço da API
- Serviço do PostgreSQL
- Healthcheck do PostgreSQL
- Volume para persistência dos dados
- Variáveis de ambiente
- Dependência adequada entre os serviços

Após a inicialização, a documentação Swagger deverá estar disponível em:

```text
http://localhost:8000/docs
```

A aplicação não deverá depender de configurações manuais após sua inicialização, além da criação do arquivo de variáveis de ambiente quando documentada.

## Estrutura sugerida

Não é obrigatório seguir exatamente esta estrutura, mas a separação de responsabilidades será avaliada:

```text
app/
├── api/
│   ├── dependencies.py
│   └── routes/
├── core/
│   ├── config.py
│   └── security.py
├── models/
├── repositories/
├── schemas/
├── services/
├── database.py
└── main.py

alembic/
tests/
.env.example
Dockerfile
docker-compose.yml
pyproject.toml
README.md
```

## Testes obrigatórios

Implemente testes automatizados para, no mínimo:

- Cadastro de usuário.
- Tentativa de cadastro com e-mail duplicado.
- Login com credenciais válidas.
- Login com credenciais inválidas.
- Acesso a uma rota protegida sem JWT.
- Criação de projeto.
- Tentativa de acesso ao projeto de outro usuário.
- Criação de tarefa com dados válidos.
- Criação de tarefa com dados inválidos.
- Atualização parcial de tarefa.
- Paginação e combinação de filtros.
- Exclusão de projeto e de suas tarefas relacionadas.

Os testes deverão ser executados por um comando documentado, por exemplo:

```bash
pytest
```

## Entrega

A solução deverá ser entregue em um repositório Git contendo:

- Código-fonte da aplicação.
- Histórico de commits.
- Este `README.md` com instruções para execução.
- Arquivo `.env.example` sem informações sensíveis.
- Migrations do banco de dados.
- Testes automatizados.
- Documentação Swagger funcional.
- Exemplos de requisições ou coleção Postman, opcionalmente.

### Prazo sugerido

De 3 a 5 dias corridos.

## Critérios de avaliação

| Critério | Peso |
| --- | ---: |
| Organização e arquitetura | 20% |
| Modelagem do banco e qualidade das consultas | 15% |
| Autenticação, autorização e segurança | 15% |
| Uso correto de FastAPI e Pydantic | 15% |
| Testes automatizados | 15% |
| Docker e execução do ambiente | 10% |
| Tratamento de erros e documentação | 10% |

Serão observados especialmente:

- Separação entre autenticação e autorização.
- Organização das responsabilidades da aplicação.
- Segurança no armazenamento de senhas e uso do JWT.
- Ausência de dados sensíveis nas respostas e no repositório.
- Paginação executada pelo banco de dados.
- Prevenção de consultas desnecessárias.
- Uso adequado de transações e constraints.
- Migrations reproduzíveis.
- Clareza, independência e qualidade dos testes.
- Qualidade das decisões técnicas documentadas.

## Diferenciais

Os itens abaixo são opcionais e não devem ser necessários para atingir a nota máxima nos requisitos principais:

- Refresh token com rotação ou revogação.
- Paginação por cursor.
- Testes de integração executados em containers.
- Logs estruturados.
- Endpoint de healthcheck da aplicação.
- Pipeline de integração contínua.
- Configuração de lint e análise estática.
- Controle otimista de concorrência.
- Documentação das decisões técnicas e melhorias futuras.

## Observações

- A qualidade da solução é mais importante do que a quantidade de funcionalidades adicionais.
- Decisões técnicas relevantes deverão ser explicadas no `README.md` da entrega.
- Caso algum requisito não seja concluído, descreva o que faltou, o motivo e como seria implementado.
- Não inclua senhas, chaves privadas, tokens ou outros segredos no repositório.
