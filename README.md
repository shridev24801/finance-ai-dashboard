# FinTrack · AI Financial Dashboard

FastAPI and MySQL backend with a Bootstrap/Jinja dashboard for small business income, expenses, customers, invoices, and payments.

## Features

- JWT bearer authentication, PBKDF2 password hashes, and admin/staff roles (first registered user is admin; later public registrations are staff).
- Role-based access: staff can manage daily customer, transaction, invoice, and payment records; admins also control deletions, dashboard totals, reports, AI insights, and member access.
- Customer, transaction, invoice, and payment CRUD APIs with validation and paginated listing.
- Invoice totals calculated on the server from item quantities and unit prices; tax is a percentage.
- Payment balance checks and automatic paid/overdue reconciliation.
- Dashboard summary, basic reports, explainable cash-flow estimate, and expense anomaly insights.
- Bootstrap pages for sign-in, registration, dashboard, and record listings.

## Setup

Use Python 3.14 and the project virtual environment:

```powershell
cd \ai-dashboard
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start MySQL in XAMPP and create/select the `ai_dashboard` database. Configure `app/.env` or the process environment:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=ai_dashboard
DB_USERNAME=root
DB_PASSWORD=
JWT_SECRET_KEY=replace-with-a-long-random-secret
```

Keep the JWT key private and use a different value per environment. Existing tables are expected to match the models; `create_all` creates missing tables but does not migrate existing tables.

Run:

```powershell
python -m uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/> for the dashboard, <http://127.0.0.1:8000/login> to sign in, and <http://127.0.0.1:8000/docs> for Swagger.

## API

Administrators have full access, including dashboard, reporting, insights, deletions, and `/api/auth/users` member management. Staff can create, view, and edit customers, transactions, invoices, and payments, but cannot delete records or access aggregate financial endpoints. Manage member roles and active status from the administrator-only Team access page. At least one active administrator must remain.

Auth: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`.

Authenticated resources: `/api/customers`, `/api/transactions`, `/api/invoices`, `/api/payments` (each provides create/list/get/update/delete). Lists accept `page` and `per_page` (max 100), and resource-specific search/filter/sort parameters. Send `Authorization: Bearer <access_token>`.

Dashboard: `GET /api/dashboard/summary`. Reports: `/api/reports/income-expense`, `/api/reports/outstanding-invoices`, `/api/reports/customer-summary`. Insights: `/api/ai/cash-flow-prediction` and `/api/ai/expense-insights`.

Cash-flow prediction averages the latest three observed monthly net cash-flow totals, or the two available months with a limited-confidence label; fewer than two months returns an insufficient-data message. Expense insights use a category average plus two standard deviations as a basic signal when at least three expense records exist. These are simple statistical signals, not investment or accounting advice. See [USER_GUIDE.md](USER_GUIDE.md) for the business workflows and calculation details.

## Notes

There is no default account. Register the first account to create the administrator, then sign in. Never expose an unauthenticated database or production secret. Run tests with `python -m pytest` after installing requirements.
