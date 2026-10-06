import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    os.environ["JWT_SECRET_KEY"] = "test-only-key-with-sufficient-entropy"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def bearer(client):
    response = client.post("/api/auth/register", json={"name": "Test Admin", "email": "admin@example.com", "password": "password-long-enough"})
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_registration_validation_and_login(client):
    # This mirrors the broken frontend payload: the missing name must be explained.
    invalid = client.post("/api/auth/register", json={"email": "new@example.com", "password": "long-enough-password"})
    assert invalid.status_code == 422
    assert "name" in invalid.json()["detail"].lower()

    payload = {"name": "New User", "email": "new@example.com", "password": "long-enough-password"}
    registered = client.post("/api/auth/register", json=payload)
    assert registered.status_code == 201, registered.text
    assert registered.json()["user"]["name"] == payload["name"]

    logged_in = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert logged_in.status_code == 200, logged_in.text
    assert logged_in.json()["access_token"]


def test_auth_and_customer_crud(client):
    headers = bearer(client)
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    created = client.post("/api/customers", headers=headers, json={"name": "Acme", "email": "accounts@example.com"})
    assert created.status_code == 201
    customer_id = created.json()["id"]
    assert client.get("/api/customers?search=Acme", headers=headers).json()["total"] == 1
    assert client.get(f"/api/customers/{customer_id}", headers=headers).status_code == 200
    updated = client.put(f"/api/customers/{customer_id}", headers=headers, json={"name": "Acme Updated", "status": "inactive"})
    assert updated.status_code == 200 and updated.json()["name"] == "Acme Updated"
    assert client.delete(f"/api/customers/{customer_id}", headers=headers).status_code == 204


def test_transaction_invoice_payment_and_summary(client):
    headers = bearer(client)
    customer = client.post("/api/customers", headers=headers, json={"name": "Acme"}).json()
    txn = client.post("/api/transactions", headers=headers, json={"type": "income", "category": "Sales", "amount": 100, "transaction_date": "2026-10-01"})
    assert txn.status_code == 201
    assert client.put(f"/api/transactions/{txn.json()['id']}", headers=headers, json={"type": "income", "category": "Sales", "amount": 100, "transaction_date": "2026-10-01"}).status_code == 200
    invoice = client.post("/api/invoices", headers=headers, json={"invoice_number": "INV-1", "customer_id": customer["id"], "invoice_date": "2026-10-01", "due_date": "2026-10-20", "tax": 10, "items": [{"description": "Service", "quantity": 2, "unit_price": 50}]})
    assert invoice.status_code == 201, invoice.text
    assert float(invoice.json()["total_amount"]) == 110
    listed_invoice = client.get("/api/invoices?search=INV-1", headers=headers).json()["items"][0]
    assert listed_invoice["id"] == invoice.json()["id"]
    assert listed_invoice["customer"]["name"] == "Acme"
    invoice_update = {"invoice_number": "INV-1", "customer_id": customer["id"], "invoice_date": "2026-10-01", "due_date": "2026-10-20", "tax": 10, "notes": "Updated", "items": [{"description": "Service", "quantity": 2, "unit_price": 50}]}
    assert client.put(f"/api/invoices/{invoice.json()['id']}", headers=headers, json=invoice_update).status_code == 200
    payment = client.post("/api/payments", headers=headers, json={"invoice_id": invoice.json()["id"], "amount": 110, "payment_date": "2026-10-02", "payment_method": "upi"})
    assert payment.status_code == 201, payment.text
    too_much = client.post("/api/payments", headers=headers, json={"invoice_id": invoice.json()["id"], "amount": 1, "payment_date": "2026-10-02", "payment_method": "upi"})
    assert too_much.status_code == 422
    assert client.get(f"/api/invoices/{invoice.json()['id']}", headers=headers).json()["items"][0]["description"] == "Service"
    assert client.get("/api/dashboard/revenue-expenses", headers=headers).status_code == 200
    assert client.get("/api/dashboard/cash-flow", headers=headers).status_code == 200
    assert client.get("/api/dashboard/invoice-status", headers=headers).status_code == 200
    assert client.get("/api/dashboard/expense-categories", headers=headers).status_code == 200
    assert client.get("/api/reports/income-expense", headers=headers).status_code == 200
    assert client.get("/api/reports/outstanding-invoices", headers=headers).status_code == 200
    assert client.get("/api/reports/customer-summary", headers=headers).status_code == 200
    assert client.get("/api/ai/cash-flow-prediction", headers=headers).status_code == 200
    assert client.get("/api/ai/expense-insights", headers=headers).status_code == 200
    assert client.get("/api/dashboard/summary", headers=headers).json()["revenue"] == 100
    assert client.delete(f"/api/payments/{payment.json()['payment']['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/transactions/{txn.json()['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/invoices/{invoice.json()['id']}", headers=headers).status_code == 204


def test_financial_pages_render(client):
    for path in ("/dashboard", "/customers", "/transactions", "/invoices", "/payments", "/reports", "/ai-insights", "/login", "/register"):
        response = client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"


def test_cash_flow_prediction_uses_two_month_history(client):
    headers = bearer(client)
    for amount, day in ((1200, "2026-08-05"), (1800, "2026-09-05")):
        response = client.post("/api/transactions", headers=headers, json={
            "type": "income", "category": "Sales", "amount": amount,
            "transaction_date": day, "status": "completed",
        })
        assert response.status_code == 201
    prediction = client.get("/api/ai/cash-flow-prediction", headers=headers)
    assert prediction.status_code == 200
    data = prediction.json()
    assert data["confidence"] == "limited"
    assert data["historical_months"] == 2
    assert data["periods"][0]["predicted_net_cash_flow"] == 1500
    assert "Limited confidence" in data["method"]
