from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.services.security import get_current_user, require_admin


router = APIRouter(
    prefix="/api/customers",
    tags=["Customers"]
    , dependencies=[Depends(get_current_user)]
)


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(
    customer: CustomerCreate,
    db: Session = Depends(get_db)
):
    new_customer = Customer(
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        company_name=customer.company_name,
        address=customer.address,
        status=customer.status
    )

    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

    return new_customer


@router.get("")
def get_customers(
    search: str | None = None,
    status: str | None = None,
    sort_by: str = Query("created_at", pattern="^(name|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Customer)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Customer.name.ilike(term), Customer.email.ilike(term), Customer.company_name.ilike(term)))
    if status:
        query = query.filter(Customer.status == status)
    column = getattr(Customer, sort_by)
    query = query.order_by(column.asc() if sort_order == "asc" else column.desc())
    total = query.count()
    customers = query.offset((page - 1) * per_page).limit(per_page).all()
    return {"items": customers, "page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.invoices:
        raise HTTPException(status_code=409, detail="Customer has invoices and cannot be deleted")
    db.delete(customer)
    db.commit()
    return Response(status_code=204)

    return customers
