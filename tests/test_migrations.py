from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.database import Base
from tests.conftest import engine


def test_migrations_match_models():
    """As migrations aplicadas devem produzir exatamente o schema declarado nos models (sem drift)."""
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(migration_context, Base.metadata)

    assert diff == []
