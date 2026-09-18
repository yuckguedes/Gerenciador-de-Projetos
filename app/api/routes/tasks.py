from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from app.api.dependencies import get_current_user, get_db, get_owned_project, get_owned_task
from app.core.cursor import InvalidCursor
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.repositories.task_repository import list_tasks_by_cursor, list_tasks_paginated
from app.schemas.pagination import CursorPaginatedResponse, PaginatedResponse
from app.schemas.task import TaskCreate, TaskFilterParams, TaskResponse, TaskUpdate

router = APIRouter(tags=["tasks"])


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: UUID,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_project(project_id, db, current_user)  # valida que o projeto é do usuário
    task = Task(**payload.model_dump(), project_id=project_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/projects/{project_id}/tasks", response_model=PaginatedResponse[TaskResponse])
def list_tasks(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: TaskStatus | None = Query(None),
    priority: TaskPriority | None = Query(None),
    search: str | None = Query(None),
    order_by: Literal["created_at", "updated_at", "due_date", "title", "priority"] = Query("created_at"),
    direction: Literal["asc", "desc"] = Query("desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_project(project_id, db, current_user)  # valida dono do projeto

    filters = TaskFilterParams(
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        search=search,
        order_by=order_by,
        direction=direction,
    )

    items, total, total_pages = list_tasks_paginated(db, project_id, filters)

    return PaginatedResponse(
        items=items,
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/projects/{project_id}/tasks/cursor", response_model=CursorPaginatedResponse[TaskResponse])
def list_tasks_cursor(
    project_id: UUID,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    status: TaskStatus | None = Query(None),
    priority: TaskPriority | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_project(project_id, db, current_user)  # valida dono do projeto

    try:
        items, next_cursor, has_more = list_tasks_by_cursor(
            db, project_id, limit=limit, cursor=cursor, status=status, priority=priority, search=search
        )
    except InvalidCursor:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CURSOR", "message": "Cursor inválido"},
        ) from None

    return CursorPaginatedResponse(items=items, next_cursor=next_cursor, has_more=has_more)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_owned_task(task_id, db, current_user)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = get_owned_task(task_id, db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = get_owned_task(task_id, db, current_user)
    db.delete(task)
    db.commit()
