from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.time import utcnow
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.token import LoginRequest, LogoutRequest, RefreshRequest, Token
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token_pair(db: Session, user_id) -> Token:
    access_token = create_access_token(subject=str(user_id))

    raw_refresh_token = generate_refresh_token()
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh_token)
    db.commit()

    return Token(access_token=access_token, refresh_token=raw_refresh_token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_ALREADY_REGISTERED", "message": "E-mail já cadastrado"},
        )

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "E-mail ou senha inválidos"},
        )

    return _issue_token_pair(db, user.id)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    invalid_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token inválido ou expirado"},
    )

    token_hash = hash_refresh_token(payload.refresh_token)
    stored_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if stored_token is None:
        raise invalid_exception

    if stored_token.revoked_at is not None:
        # reuso de um refresh token já rotacionado/revogado: sinal de possível roubo de token.
        # revoga todos os tokens ativos do usuário como medida de contenção.
        db.query(RefreshToken).filter(
            RefreshToken.user_id == stored_token.user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": utcnow()})
        db.commit()
        raise invalid_exception

    if stored_token.expires_at <= utcnow():
        raise invalid_exception

    new_token_pair = _issue_token_pair(db, stored_token.user_id)

    new_raw_token = new_token_pair.refresh_token
    new_token_hash = hash_refresh_token(new_raw_token)
    new_token_row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == new_token_hash))
    assert new_token_row is not None  # acabamos de inserir essa linha em _issue_token_pair

    stored_token.revoked_at = utcnow()
    stored_token.replaced_by_id = new_token_row.id
    db.commit()

    return new_token_pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)):
    token_hash = hash_refresh_token(payload.refresh_token)
    stored_token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if stored_token is not None and stored_token.revoked_at is None:
        stored_token.revoked_at = utcnow()
        db.commit()


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
