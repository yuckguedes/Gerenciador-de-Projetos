"""use text for project and task descriptions

Revision ID: b3c1d5e7a9f2
Revises: 88f64bd1a65c
Create Date: 2026-09-18 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c1d5e7a9f2'
down_revision: Union[str, None] = '88f64bd1a65c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # o enunciado não limita o tamanho da descrição; com VARCHAR(500) uma descrição maior
    # estourava no banco e virava 500 na API.
    op.alter_column('projects', 'description', existing_type=sa.String(length=500), type_=sa.Text(), existing_nullable=True)
    op.alter_column('tasks', 'description', existing_type=sa.String(length=500), type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    # falha se já existirem descrições com mais de 500 caracteres
    op.alter_column('tasks', 'description', existing_type=sa.Text(), type_=sa.String(length=500), existing_nullable=True)
    op.alter_column('projects', 'description', existing_type=sa.Text(), type_=sa.String(length=500), existing_nullable=True)
