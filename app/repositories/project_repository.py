from math import ceil
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.project import Project


def list_projects_paginated(db: Session, owner_id: UUID, page: int, page_size: int):
    query = db.query(Project).filter(Project.owner_id == owner_id)

    total = query.count()

    # Project.id como desempate: sem ele, projetos com o mesmo created_at não têm ordem estável
    # e podem se repetir ou sumir entre páginas
    items = (
        query.order_by(Project.created_at.desc(), Project.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    total_pages = ceil(total / page_size) if total else 0

    return items, total, total_pages
