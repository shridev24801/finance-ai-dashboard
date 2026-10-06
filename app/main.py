from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import date
from collections import defaultdict
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config.database import Base, engine
from app.models import (
    User,
    Customer,
    Transaction,
    Invoice,
    InvoiceItem,
    Payment
)

from app.routers.customers import router as customer_router
from app.routers.auth import router as auth_router
from app.routers.transactions import router as transaction_router
from app.routers.invoices import router as invoice_router
from app.routers.payments import router as payment_router
from app.services.security import get_current_user
from app.config.database import get_db
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.customer import Customer


app = FastAPI(
    title="AI Dashboard",
    version="1.0.0"
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(part) for part in error["loc"] if part not in ("body", "query", "path")),
         "message": error["msg"]}
        for error in exc.errors()
    ]
    message = "; ".join(f"{error['field']}: {error['message']}" if error["field"] else error["message"] for error in errors)
    return JSONResponse(status_code=422, content={"detail": message or "Request validation failed", "errors": errors})


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


app.include_router(customer_router)
app.include_router(auth_router)
app.include_router(transaction_router)
app.include_router(invoice_router)
app.include_router(payment_router)


@app.get("/")
def home():
    return RedirectResponse("/dashboard")


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})


@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={})


@app.get("/{page}")
def app_page(page: str, request: Request):
    titles = {"dashboard": "Dashboard", "customers": "Customers", "transactions": "Transactions", "invoices": "Invoices", "payments": "Payments", "reports": "Reports", "ai-insights": "AI Insights"}
    if page not in titles:
        from fastapi import HTTPException
        raise HTTPException(404, "Page not found")
    template = {"dashboard": "dashboard.html", "reports": "reports.html", "ai-insights": "ai_insights.html"}.get(page, "records.html")
    return templates.TemplateResponse(request=request, name=template, context={"title": titles[page]})


@app.get("/api/dashboard/summary")
def dashboard_summary(user=Depends(get_current_user), db: Session = Depends(get_db)):
    revenue = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(Transaction.type == "income", Transaction.status == "completed").scalar()
    expenses = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(Transaction.type == "expense", Transaction.status == "completed").scalar()
    invoices = db.query(Invoice).filter(Invoice.status != "cancelled").all()
    outstanding = sum((max(0, float(i.total_amount) - sum(float(p.amount) for p in i.payments if p.status == "completed")) for i in invoices), 0)
    return {"revenue": float(revenue), "expenses": float(expenses), "profit": float(revenue) - float(expenses),
            "outstanding": outstanding, "invoice_count": len(invoices), "customer_count": db.query(Customer).count()}


def monthly_transaction_totals(db: Session):
    result = defaultdict(lambda: {"revenue": 0.0, "expenses": 0.0})
    rows = db.query(Transaction).filter(Transaction.status == "completed").all()
    for row in rows:
        month = row.transaction_date.strftime("%Y-%m")
        key = "revenue" if row.type == "income" else "expenses"
        result[month][key] += float(row.amount)
    return [{"month": key, **values, "cash_flow": values["revenue"] - values["expenses"]} for key, values in sorted(result.items())[-12:]]


@app.get("/api/dashboard/revenue-expenses")
def dashboard_revenue_expenses(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return monthly_transaction_totals(db)


@app.get("/api/dashboard/cash-flow")
def dashboard_cash_flow(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"month": row["month"], "cash_flow": row["cash_flow"]} for row in monthly_transaction_totals(db)]


@app.get("/api/dashboard/invoice-status")
def dashboard_invoice_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    counts = defaultdict(int)
    for invoice in db.query(Invoice).all(): counts[invoice.status] += 1
    return [{"status": key, "count": value} for key, value in sorted(counts.items())]


@app.get("/api/dashboard/expense-categories")
def dashboard_expense_categories(user=Depends(get_current_user), db: Session = Depends(get_db)):
    totals = defaultdict(float)
    for row in db.query(Transaction).filter(Transaction.type == "expense", Transaction.status == "completed").all():
        totals[row.category] += float(row.amount)
    return [{"category": key, "amount": value} for key, value in sorted(totals.items(), key=lambda pair: pair[1], reverse=True)]


@app.get("/api/reports/income-expense")
def income_expense(start_date: date | None = None, end_date: date | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Transaction).filter(Transaction.status == "completed")
    if start_date: q = q.filter(Transaction.transaction_date >= start_date)
    if end_date: q = q.filter(Transaction.transaction_date <= end_date)
    rows = q.all(); sums = {"income": 0.0, "expense": 0.0}; categories = defaultdict(float); monthly = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for row in rows:
        amount = float(row.amount); sums[row.type] += amount
        if row.type == "expense": categories[row.category] += amount
        monthly[row.transaction_date.strftime("%Y-%m")][row.type] += amount
    return {**sums, "profit": sums["income"] - sums["expense"], "transaction_count": len(rows),
            "expense_categories": [{"category": k, "amount": v} for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)],
            "monthly": [{"month": k, **v} for k, v in sorted(monthly.items())]}


@app.get("/api/reports/outstanding-invoices")
def outstanding_report(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Invoice).filter(Invoice.status.notin_(["cancelled", "paid"])).all()
    return [{"invoice_id": i.id, "invoice_number": i.invoice_number, "customer_id": i.customer_id,
             "total_amount": float(i.total_amount), "paid": sum(float(p.amount) for p in i.payments if p.status == "completed"),
             "due_date": i.due_date} for i in rows]


@app.get("/api/reports/customer-summary")
def customer_report(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"customer_id": c.id, "name": c.name, "invoice_count": len(c.invoices),
             "billed": sum(float(i.total_amount) for i in c.invoices)} for c in db.query(Customer).all()]


@app.get("/api/ai/cash-flow-prediction")
def cash_flow_prediction(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from collections import defaultdict
    months = defaultdict(float)
    transactions = db.query(Transaction).filter(Transaction.status == "completed").all()
    for row in transactions:
        month = row.transaction_date.strftime("%Y-%m")
        months[month] += float(row.amount) * (1 if row.type == "income" else -1)
    history = sorted(months.items())
    if len(history) < 2:
        return {"message": "Not enough historical data to generate a prediction. Record completed transactions across at least two different months.", "periods": []}
    # Use only completed, observed data. With two months a forecast is possible,
    # but confidence is limited; with three or more, average the latest three.
    sample = history[-3:]
    prediction = sum(value for _, value in sample) / len(sample)
    limited = len(history) == 2
    method = f"Mean net cash flow across the latest {len(sample)} observed months."
    if limited:
        method += " Limited confidence: based on only two months; treat as a directional estimate."
    return {"method": method, "confidence": "limited" if limited else "moderate",
            "historical_months": len(history), "completed_transaction_count": len(transactions),
            "periods": [{"month": "next_month", "predicted_net_cash_flow": round(prediction, 2)}]}


@app.get("/api/ai/expense-insights")
def expense_insights(user=Depends(get_current_user), db: Session = Depends(get_db)):
    from collections import defaultdict
    import statistics
    categories = defaultdict(list)
    for row in db.query(Transaction).filter(Transaction.type == "expense", Transaction.status == "completed").all():
        categories[row.category].append(float(row.amount))
    insights = []
    for category, values in categories.items():
        if len(values) < 3: continue
        mean = statistics.mean(values); sd = statistics.stdev(values)
        threshold = mean + 2 * sd
        if sd and values[-1] > threshold:
            insights.append({"category": category, "latest_amount": values[-1], "usual_mean": round(mean, 2), "threshold": round(threshold, 2)})
    return {"method": "category-level mean plus two standard deviations; at least three observations required", "unusual_expenses": insights}
