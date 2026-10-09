from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionInput, TransactionResponse
from app.services.security import get_current_user, require_admin

router = APIRouter(prefix="/api/transactions", tags=["Transactions"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=TransactionResponse, status_code=201)
def create(data: TransactionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = Transaction(**data.model_dump(), created_by=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return row


@router.get("")
def listing(search: str | None = None, type: str | None = Query(None, pattern="^(income|expense)$"), category: str | None = None,
            status: str | None = None, start_date: date | None = None, end_date: date | None = None,
            sort_by: str = Query("transaction_date", pattern="^(transaction_date|amount)$"),
            sort_order: str = Query("desc", pattern="^(asc|desc)$"), page: int = Query(1, ge=1),
            per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    q = db.query(Transaction)
    if search:
        term = f"%{search}%"; q = q.filter(or_(Transaction.description.ilike(term), Transaction.category.ilike(term), Transaction.reference.ilike(term)))
    if type: q = q.filter(Transaction.type == type)
    if category: q = q.filter(Transaction.category.ilike(f"%{category}%"))
    if status: q = q.filter(Transaction.status == status)
    if start_date: q = q.filter(Transaction.transaction_date >= start_date)
    if end_date: q = q.filter(Transaction.transaction_date <= end_date)
    col = getattr(Transaction, sort_by); q = q.order_by(col.asc() if sort_order == "asc" else col.desc())
    total = q.count(); items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}


@router.get("/{row_id}", response_model=TransactionResponse)
def get_one(row_id: int, db: Session = Depends(get_db)):
    row = db.get(Transaction, row_id)
    if not row: raise HTTPException(404, "Transaction not found")
    return row


@router.put("/{row_id}", response_model=TransactionResponse)
def update(row_id: int, data: TransactionInput, db: Session = Depends(get_db)):
    row = db.get(Transaction, row_id)
    if not row: raise HTTPException(404, "Transaction not found")
    for key, value in data.model_dump().items(): setattr(row, key, value)
    db.commit(); db.refresh(row); return row


@router.delete("/{row_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete(row_id: int, db: Session = Depends(get_db)):
    row = db.get(Transaction, row_id)
    if not row: raise HTTPException(404, "Transaction not found")
    db.delete(row); db.commit(); return Response(status_code=204)
