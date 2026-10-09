from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.user import User
from app.schemas.invoice import InvoiceInput, InvoiceResponse
from app.services.permissions import require_permission
from app.services.security import get_current_user

router = APIRouter(prefix="/api/invoices", tags=["Invoices"], dependencies=[Depends(get_current_user)])
CENT = Decimal("0.01")


def amounts(data: InvoiceInput):
    subtotal = sum((i.unit_price * i.quantity for i in data.items), Decimal(0)).quantize(CENT, rounding=ROUND_HALF_UP)
    tax_amount = (subtotal * data.tax / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return subtotal, tax_amount, subtotal + tax_amount


def update_workflow_status(invoice: Invoice):
    paid = sum((Decimal(str(payment.amount)) for payment in invoice.payments if payment.status == "completed"), Decimal(0))
    if paid >= Decimal(str(invoice.total_amount)):
        invoice.status = "paid"
    elif invoice.status == "sent" and invoice.due_date.date() < date.today():
        invoice.status = "overdue"


@router.post("", response_model=InvoiceResponse, status_code=201, dependencies=[Depends(require_permission("invoices.create"))])
def create(data: InvoiceInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.due_date < data.invoice_date: raise HTTPException(422, "Due date must be on or after invoice date")
    if data.status in ("paid", "overdue"): raise HTTPException(422, "Paid and overdue statuses are managed by the payment and due-date workflow")
    if not db.get(Customer, data.customer_id): raise HTTPException(404, "Customer not found")
    if db.query(Invoice).filter_by(invoice_number=data.invoice_number).first(): raise HTTPException(409, "Invoice number already exists")
    subtotal, tax, total = amounts(data)
    invoice = Invoice(invoice_number=data.invoice_number, customer_id=data.customer_id, invoice_date=data.invoice_date,
                      due_date=data.due_date, subtotal=subtotal, tax=tax, total_amount=total,
                      status=data.status, notes=data.notes, created_by=user.id)
    invoice.items = [InvoiceItem(description=i.description, quantity=i.quantity, unit_price=i.unit_price,
                                 amount=(i.unit_price * i.quantity).quantize(CENT)) for i in data.items]
    db.add(invoice); db.commit(); db.refresh(invoice); return invoice


@router.get("", dependencies=[Depends(require_permission("invoices.view"))])
def listing(search: str | None = None, status: str | None = None, customer_id: int | None = None,
            start_date: date | None = None, end_date: date | None = None,
            sort_by: str = Query("invoice_date", pattern="^(invoice_number|invoice_date|total_amount)$"),
            sort_order: str = Query("desc", pattern="^(asc|desc)$"), page: int = Query(1, ge=1),
            per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    q = db.query(Invoice).options(joinedload(Invoice.items), joinedload(Invoice.customer))
    if search:
        term = f"%{search}%"; q = q.join(Customer).filter(or_(Invoice.invoice_number.ilike(term), Customer.name.ilike(term)))
    if status: q = q.filter(Invoice.status == status)
    if customer_id: q = q.filter(Invoice.customer_id == customer_id)
    if start_date: q = q.filter(Invoice.invoice_date >= start_date)
    if end_date: q = q.filter(Invoice.invoice_date <= end_date)
    col = getattr(Invoice, sort_by); q = q.order_by(col.asc() if sort_order == "asc" else col.desc())
    total = q.count(); rows = q.offset((page - 1) * per_page).limit(per_page).all()
    for row in rows: update_workflow_status(row)
    db.commit()
    items = [{
        "id": row.id,
        "invoice_number": row.invoice_number,
        "customer_id": row.customer_id,
        "customer": {"id": row.customer.id, "name": row.customer.name} if row.customer else None,
        "invoice_date": row.invoice_date,
        "due_date": row.due_date,
        "subtotal": row.subtotal,
        "tax": row.tax,
        "total_amount": row.total_amount,
        "status": row.status,
        "notes": row.notes,
        "items": [{"id": item.id, "description": item.description, "quantity": item.quantity,
                   "unit_price": item.unit_price, "amount": item.amount} for item in row.items],
    } for row in rows]
    return {"items": items, "page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}


@router.get("/{invoice_id}", response_model=InvoiceResponse, dependencies=[Depends(require_permission("invoices.view"))])
def get_one(invoice_id: int, db: Session = Depends(get_db)):
    row = db.query(Invoice).options(joinedload(Invoice.items)).filter_by(id=invoice_id).first()
    if not row: raise HTTPException(404, "Invoice not found")
    update_workflow_status(row)
    db.commit()
    return row


@router.put("/{invoice_id}", response_model=InvoiceResponse, dependencies=[Depends(require_permission("invoices.edit"))])
def update(invoice_id: int, data: InvoiceInput, db: Session = Depends(get_db)):
    row = db.query(Invoice).options(joinedload(Invoice.items)).filter_by(id=invoice_id).first()
    if not row: raise HTTPException(404, "Invoice not found")
    if data.due_date < data.invoice_date: raise HTTPException(422, "Due date must be on or after invoice date")
    if data.status in ("paid", "overdue"): raise HTTPException(422, "Paid and overdue statuses are managed by the payment and due-date workflow")
    if not db.get(Customer, data.customer_id): raise HTTPException(404, "Customer not found")
    duplicate = db.query(Invoice).filter(Invoice.invoice_number == data.invoice_number, Invoice.id != invoice_id).first()
    if duplicate: raise HTTPException(409, "Invoice number already exists")
    subtotal, tax, total = amounts(data)
    for key, value in {"invoice_number": data.invoice_number, "customer_id": data.customer_id, "invoice_date": data.invoice_date,
                       "due_date": data.due_date, "subtotal": subtotal, "tax": tax, "total_amount": total,
                       "status": data.status, "notes": data.notes}.items(): setattr(row, key, value)
    row.items.clear()
    row.items.extend(InvoiceItem(description=i.description, quantity=i.quantity, unit_price=i.unit_price,
                                 amount=(i.unit_price * i.quantity).quantize(CENT)) for i in data.items)
    db.commit(); db.refresh(row); return row


@router.delete("/{invoice_id}", status_code=204, dependencies=[Depends(require_permission("invoices.delete"))])
def delete(invoice_id: int, db: Session = Depends(get_db)):
    row = db.get(Invoice, invoice_id)
    if not row: raise HTTPException(404, "Invoice not found")
    if row.payments: raise HTTPException(409, "Invoice with payments cannot be deleted")
    db.delete(row); db.commit(); return Response(status_code=204)
