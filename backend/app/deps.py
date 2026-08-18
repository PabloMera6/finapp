from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token


def get_current_user(
    finapp_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Protege rutas exigiendo una cookie de sesion valida (HTTPOnly).
    No existe ningun endpoint de datos financieros sin esta dependencia.
    """
    if not finapp_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    user_id = decode_access_token(finapp_session)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion invalida o expirada")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user
