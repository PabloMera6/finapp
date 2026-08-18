from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


@router.post("/login")
@limiter.limit("5/minute")  # rate limiting en login (sección 5)
def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")

    token = create_access_token(subject=user.id)
    response.set_cookie(
        key="finapp_session",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return {"email": user.email}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("finapp_session", path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"email": user.email}
