from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Category, Subcategory, User

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    categories = db.query(Category).order_by(Category.name).all()
    result = []
    for c in categories:
        subs = db.query(Subcategory).filter(Subcategory.category_id == c.id).order_by(Subcategory.name).all()
        result.append({"id": c.id, "name": c.name, "subcategories": [{"id": s.id, "name": s.name} for s in subs]})
    return result
