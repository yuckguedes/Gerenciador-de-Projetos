from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.core.time import utcnow
from app.models.task import TaskStatus, TaskPriority


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str | None = None
    priority: TaskPriority
    due_date: datetime | None = None

    @field_validator("due_date")
    @classmethod
    def due_date_not_past(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            now = datetime.now(v.tzinfo) if v.tzinfo else utcnow()
            if v < now:
                raise ValueError("due_date não pode ser uma data no passado")
        return v


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None

    @field_validator("due_date")
    @classmethod
    def due_date_not_past(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            now = datetime.now(v.tzinfo) if v.tzinfo else utcnow()
            if v < now:
                raise ValueError("due_date não pode ser uma data no passado")
        return v


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    project_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskFilterParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    search: str | None = None
    order_by: Literal["created_at", "updated_at", "due_date", "title", "priority"] = "created_at"
    direction: Literal["asc", "desc"] = "desc"
