from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.recurring_detector import detect_recurring

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


@router.get("")
def get_recurring(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = detect_recurring(db, user.id)
    total = sum(i["average_amount"] for i in items)
    return {"items": items, "total_monthly": round(total, 2)}
