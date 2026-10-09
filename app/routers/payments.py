from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.user import User
from app.schemas.invoice import PaymentInput
from app.services.security import get_current_user, require_admin

router = APIRouter(prefix="/api/payments", tags=["Payments"], dependencies=[Depends(get_current_user)])


def reconcile(invoice: Invoice, db: Session):
    paid = sum((Decimal(str(p.amount)) for p in invoice.payments if p.status == "completed"), Decimal(0))
    if paid >= Decimal(str(invoice.total_amount)): invoice.status = "paid"
    elif invoice.due_date.date() < date.today() and invoice.status not in ("draft", "cancelled"): invoice.status = "overdue"
    elif invoice.status == "paid": invoice.status = "sent"


@router.post("", status_code=201)
def create(data: PaymentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoice = db.query(Invoice).filter_by(id=data.invoice_id).first()
    if not invoice: raise HTTPException(404, "Invoice not found")
    if invoice.status == "cancelled": raise HTTPException(409, "Cannot pay a cancelled invoice")
    paid = sum((Decimal(str(p.amount)) for p in invoice.payments if p.status == "completed"), Decimal(0))
    remaining = Decimal(str(invoice.total_amount)) - paid
    if data.amount > remaining: raise HTTPException(422, "Payment exceeds the remaining invoice balance")
    payment = Payment(**data.model_dump(), status="completed", created_by=user.id)
    db.add(payment); db.flush(); reconcile(invoice, db); db.commit(); db.refresh(payment)
    return {"payment": payment, "remaining_balance": max(Decimal(0), remaining - data.amount)}


@router.get("")
def listing(invoice_id: int | None = None, payment_method: str | None = None, status: str | None = None,
            search: str | None = None, start_date: date | None = None, end_date: date | None = None,
            page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    q = db.query(Payment)
    if invoice_id: q = q.filter(Payment.invoice_id == invoice_id)
    if payment_method: q = q.filter(Payment.payment_method == payment_method)
    if status: q = q.filter(Payment.status == status)
    if search: q = q.filter(or_(Payment.reference.ilike(f"%{search}%"), Payment.payment_method.ilike(f"%{search}%")))
    if start_date: q = q.filter(Payment.payment_date >= start_date)
    if end_date: q = q.filter(Payment.payment_date <= end_date)
    total = q.count(); rows = q.order_by(Payment.payment_date.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": rows, "page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}


@router.get("/{payment_id}")
def get_one(payment_id: int, db: Session = Depends(get_db)):
    row = db.get(Payment, payment_id)
    if not row: raise HTTPException(404, "Payment not found")
    return row


@router.put("/{payment_id}")
def update(payment_id: int, data: PaymentInput, db: Session = Depends(get_db)):
    row = db.get(Payment, payment_id)
    if not row: raise HTTPException(404, "Payment not found")
    target = db.get(Invoice, data.invoice_id)
    if not target: raise HTTPException(404, "Invoice not found")
    paid_elsewhere = sum((Decimal(str(p.amount)) for p in target.payments if p.status == "completed" and p.id != row.id), Decimal(0))
    if paid_elsewhere + data.amount > Decimal(str(target.total_amount)): raise HTTPException(422, "Payment exceeds the remaining invoice balance")
    original = db.get(Invoice, row.invoice_id)
    for key, value in data.model_dump().items(): setattr(row, key, value)
    if original.id != target.id: reconcile(original, db)
    reconcile(target, db); db.commit(); db.refresh(row); return row


@router.delete("/{payment_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete(payment_id: int, db: Session = Depends(get_db)):
    row = db.get(Payment, payment_id)
    if not row: raise HTTPException(404, "Payment not found")
    invoice = db.get(Invoice, row.invoice_id); db.delete(row); db.flush(); reconcile(invoice, db); db.commit()
    return Response(status_code=204)
