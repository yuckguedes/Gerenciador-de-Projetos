from uuid import UUID
from math import ceil
from sqlalchemy.orm import Session
from app.models.task import Task
from app.schemas.task import TaskFilterParams


def list_tasks_paginated(db: Session, project_id: UUID, filters: TaskFilterParams):
    query = db.query(Task).filter(Task.project_id == project_id)

    if filters.status is not None:
        query = query.filter(Task.status == filters.status)

    if filters.priority is not None:
        query = query.filter(Task.priority == filters.priority)

    if filters.search:
        query = query.filter(Task.title.ilike(f"%{filters.search}%"))

    # conta APÓS os filtros, ANTES da paginação
    total = query.count()

    column = getattr(Task, filters.order_by)
    query = query.order_by(column.desc() if filters.direction == "desc" else column.asc())

    items = (
        query.offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
        .all()
    )

    total_pages = ceil(total / filters.page_size) if total else 0

    return items, total, total_pages
