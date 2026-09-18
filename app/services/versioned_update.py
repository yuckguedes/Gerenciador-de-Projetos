from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session


def apply_versioned_update[ModelT](
    db: Session,
    model: type[ModelT],
    obj: ModelT,
    changes: dict[str, Any],
    expected_version: int | None,
    conflict_message: str,
) -> ModelT:
    """Aplica `changes` em `obj` com um único UPDATE atômico e incrementa `version`.

    Se `expected_version` for informado, o UPDATE só afeta a linha quando a versão no banco ainda
    é a mesma (`WHERE version = :expected`), então duas requisições concorrentes com a mesma versão
    não passam ambas: a segunda afeta 0 linhas e recebe 409. Sem `expected_version`, a atualização
    é aplicada normalmente (last-write-wins), como no fluxo padrão do enunciado.
    """
    stmt = (
        update(model)
        .where(model.id == obj.id)  # type: ignore[attr-defined]
        .values(**changes, version=model.version + 1)  # type: ignore[attr-defined]
        .execution_options(synchronize_session=False)
    )
    if expected_version is not None:
        stmt = stmt.where(model.version == expected_version)  # type: ignore[attr-defined]

    result = db.execute(stmt)
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_CONFLICT", "message": conflict_message},
        )

    db.commit()
    db.refresh(obj)
    return obj
