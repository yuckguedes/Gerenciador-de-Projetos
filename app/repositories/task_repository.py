from math import ceil
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.cursor import decode_cursor, encode_cursor
from app.models.task import Task, TaskPriority, TaskStatus
from app.schemas.task import TaskFilterParams


def _escape_like(term: str) -> str:
    # % e _ digitados pelo usuário devem ser buscados literalmente, não tratados como curingas do LIKE
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filtered_tasks_query(
    db: Session,
    project_id: UUID,
    status: TaskStatus | None,
    priority: TaskPriority | None,
    search: str | None,
):
    query = db.query(Task).filter(Task.project_id == project_id)

    if status is not None:
        query = query.filter(Task.status == status)

    if priority is not None:
        query = query.filter(Task.priority == priority)

    if search:
        query = query.filter(Task.title.ilike(f"%{_escape_like(search)}%", escape="\\"))

    return query


def list_tasks_paginated(db: Session, project_id: UUID, filters: TaskFilterParams):
    query = _filtered_tasks_query(db, project_id, filters.status, filters.priority, filters.search)

    # conta APÓS os filtros, ANTES da paginação
    total = query.count()

    column = getattr(Task, filters.order_by)
    descending = filters.direction == "desc"
    # Task.id como desempate: sem ele, linhas com o mesmo valor de ordenação (ex.: mesma prioridade)
    # não têm ordem estável e podem se repetir ou sumir entre páginas
    query = query.order_by(
        column.desc() if descending else column.asc(),
        Task.id.desc() if descending else Task.id.asc(),
    )

    items = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size).all()

    total_pages = ceil(total / filters.page_size) if total else 0

    return items, total, total_pages


def list_tasks_by_cursor(
    db: Session,
    project_id: UUID,
    limit: int,
    cursor: str | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    search: str | None = None,
):
    query = _filtered_tasks_query(db, project_id, status, priority, search)

    if cursor is not None:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        query = query.filter(
            or_(
                Task.created_at < cursor_created_at,
                and_(Task.created_at == cursor_created_at, Task.id < cursor_id),
            )
        )

    query = query.order_by(Task.created_at.desc(), Task.id.desc())

    # busca um item a mais do que o limite, só para saber se existe próxima página
    rows = query.limit(limit + 1).all()

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None

    return items, next_cursor, has_more
