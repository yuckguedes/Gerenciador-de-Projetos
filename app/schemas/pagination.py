from typing import Generic, TypeVar, List
from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class CursorPaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    next_cursor: str | None
    has_more: bool
