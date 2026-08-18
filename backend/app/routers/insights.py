from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.insight_generator import generate_insights

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("")
def get_insights(
    year: int = Query(default=None), month: int = Query(default=None),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    return generate_insights(db, user.id, year or now.year, month or now.month)
