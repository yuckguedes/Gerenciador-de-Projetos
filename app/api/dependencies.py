from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.requests import Request
from jose import JWTError
from sqlalchemy.orm import Session
import structlog
from app.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.models.project import Project
from app.models.task import Task


class CustomHTTPBearer(HTTPBearer):
    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials:
        try:
            return await super().__call__(request)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "MISSING_TOKEN", "message": "Token de autenticação ausente"},
            )


bearer_scheme = CustomHTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_TOKEN", "message": "Token inválido ou expirado"},
    )
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception

    # request.state é compartilhado entre a task da rota e a da middleware de logging
    # (que roda a aplicação numa task separada); contextvars setadas aqui não
    # propagariam de volta para o log final da requisição, então usamos request.state
    # para essa comunicação e contextvars só para propagação dentro da própria task.
    request.state.user_id = str(user.id)
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


def get_owned_project(project_id: UUID, db: Session, current_user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "Projeto não encontrado"},
        )
    if project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PROJECT_ACCESS_DENIED", "message": "Acesso negado a este projeto"},
        )
    return project


def get_owned_task(task_id: UUID, db: Session, current_user: User) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "Tarefa não encontrada"},
        )
    if task.project.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TASK_ACCESS_DENIED", "message": "Acesso negado a esta tarefa"},
        )
    return task
