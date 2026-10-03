from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.services.match_runner import start_match

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("/{match_id}/start", status_code=202)
async def start(match_id: str, db: Session = Depends(get_db)):
    try:
        start_match(db, match_id, get_settings())
    except LookupError:
        raise HTTPException(404, "Partido no existe")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"status": "started"}