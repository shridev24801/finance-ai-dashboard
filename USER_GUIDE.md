# FinTrack User Guide

This guide explains FinTrack in everyday terms: what to enter, how the pages work, and how the figures are calculated. It is written for business owners and staff, not developers.

## What the app is for

FinTrack keeps customer details, income and expense records, invoices, and payments in one place. The dashboard and reports summarize the records you enter. The AI Insights page uses simple statistics on completed transactions to estimate cash flow and highlight possible unusually large expenses. It does not connect to a bank, send invoices, or make accounting decisions for you.

All money amounts are shown in Indian rupees (₹). Use the same currency and date practices throughout your records.

## Getting started

1. Open the FinTrack address provided for your business and choose **Create account** if you do not yet have an account.
2. Enter your name, email, and a password between 10 and 128 characters.
3. The first account registered in an empty user database is an administrator. Later public registrations are staff accounts.
4. Sign in. FinTrack keeps your sign-in token in this browser. Use **Logout** when you finish on a shared computer.
5. Add customers, then record transactions, create invoices, and enter payments as they occur.

Administrators can use **Team access** to set each staff member's role, active status, and individual capabilities. View, add, edit, and delete permissions are independently controlled for each record area. Dashboard, Reports, and AI Insights viewing are separate permissions. A staff member granted only **Reports** can view reports but cannot add, edit, or delete records. The application enforces access on the server as well as in the page navigation.

## The main pages

### Dashboard

The dashboard gives a current summary:

- **Revenue**: completed income transactions.
- **Expenses**: completed expense transactions.
- **Profit**: revenue minus expenses.
- **Outstanding**: unpaid portions of all non-cancelled invoices.
- **Invoice Count**: invoices other than cancelled invoices. Paid invoices are included in this count.
- **Customer Count**: all customers, including inactive customers.

The charts show completed income and expenses grouped by transaction month, net cash flow by month, invoice counts by status, and completed expense totals by category. Recent transactions are shown below the charts. Empty months with no completed transaction are not shown in the chart data.

### Customers

Customers are the people or organizations you bill. Add a name; email, phone, company, address, and active/inactive status are optional. Search and status filters help find records, and the list is paginated.

If your account has edit permission, you can update a customer. If it has delete permission, you can delete one. FinTrack blocks deletion when invoices are linked to that customer, so invoice history is not orphaned. Mark a customer inactive when you no longer work with them but need to keep their history.

### Transactions

Transactions are manually recorded business income or expenses. Each record has a type, category, positive amount, date, and optional description or reference. The available status choices are:

- **Completed**: included in dashboard totals, reports, charts, and AI analysis.
- **Pending**: saved for tracking, but not included in those completed-transaction calculations.
- **Cancelled**: retained as a record but excluded from those calculations.

Use **Income** for money received from business activity and **Expense** for costs. Search by description, category, or reference. Filter by type, category, status, or date range; sort by date or amount. Add, edit, and delete controls appear only when the administrator has granted those capabilities.

### Invoices

An invoice connects a customer to one or more billed items. Enter a unique invoice number, customer, invoice date, due date, tax rate, and at least one item. Each item needs a description, quantity, and unit price. The page shows a running estimate while you edit; FinTrack recalculates the saved totals on the server.

The invoice total is calculated as follows:

```text
Item amount = quantity × unit price
Subtotal = sum of all item amounts
Tax amount = subtotal × tax rate ÷ 100
Invoice total = subtotal + tax amount
```

Amounts are rounded to two decimal places. For example, one item with quantity 2 and unit price ₹500 is ₹1,000. At a 10% tax rate, tax is ₹100 and the total is ₹1,100. The tax rate is what you enter in the form; the invoice's stored/displayed tax figure is the resulting tax amount.

The due date cannot be earlier than the invoice date, and invoice numbers must be unique. Statuses mean:

- **Draft**: being prepared.
- **Sent**: marked as issued to the customer. This is a status marker; FinTrack does not email or deliver the invoice.
- **Overdue**: a sent invoice past its due date that is not fully paid. The status is refreshed when invoice data is viewed or listed.
- **Paid**: completed payments equal or exceed the invoice total. FinTrack sets this through payment reconciliation; it is not a status to set manually.
- **Cancelled**: no longer active. Cancelled invoices do not count toward outstanding balances.

Invoice details show items, total, payments, and remaining balance. An invoice with payments cannot be deleted. You can search by invoice number or customer, filter by status/date, and sort by invoice number, date, or amount.

### Payments

Record each payment against an invoice. Choose an invoice, enter the payment amount, payment date, method, and optional reference. FinTrack shows the invoice's current outstanding balance and rejects a payment larger than that balance. Supported methods are cash, bank transfer, UPI, card, and other.

The calculation is:

```text
Paid so far = sum of completed payments for the invoice
Outstanding balance = invoice total − paid so far
```

For example, a ₹1,100 invoice with a ₹400 payment has ₹700 outstanding. Once completed payments reach ₹1,100, the invoice becomes Paid. If a payment is deleted, the invoice balance and status are recalculated. Deleting a payment is permanent, so confirm the record before removing it.

**Important:** entering an invoice payment does not automatically create an income transaction. Payments update invoice balances and statuses; dashboard revenue and cash-flow charts use transactions. Record the appropriate income transaction separately if you want it included in those figures. Avoid recording the same receipt twice as income transactions.

### Reports

Choose a start and end date, then apply the range to the income/expense report. The report shows completed transaction revenue, expenses, profit, transaction count, monthly totals, and expenses by category. Use **Export CSV** to download these report totals and category figures.

The outstanding invoice list and invoice-status summary describe current invoice records; they are not limited by the transaction date range. Cancelled and paid invoices are left out of the outstanding list.

## How the totals fit together

FinTrack keeps transaction accounting and invoice collection as separate records:

```text
Revenue and expenses → completed transactions
Invoice balance       → invoice total minus its completed payments
Profit                → completed income transactions minus completed expense transactions
Cash-flow estimate    → monthly net values from completed transactions
```

As an example, if you record ₹60,000 income and ₹15,000 expenses as completed transactions, the dashboard shows ₹60,000 revenue, ₹15,000 expenses, and ₹45,000 profit. If you also have an unpaid ₹1,100 invoice, that amount contributes to Outstanding until paid or cancelled. The invoice itself does not add revenue to the Revenue card.

Use transaction dates consistently: these dates determine the month used in charts, reports, and the cash-flow estimate. Pending and cancelled transactions remain available for tracking but are excluded from completed-transaction totals.

## AI Insights: what it does

The AI Insights page is intentionally explainable. It uses the completed transaction records already in FinTrack; it does not invent missing records or use an external AI service.

### Cash-flow prediction

FinTrack adds each month's completed income and subtracts that month's completed expenses to get monthly net cash flow. It then averages the most recent observed monthly totals:

- With **two observed months**, it shows their average as a directional estimate and labels confidence **limited**.
- With **three or more observed months**, it averages the latest three and labels confidence **moderate**.
- With fewer than **two observed months**, it says there is not enough history to make a prediction.

For example, if two monthly net totals are ₹12,000 and ₹18,000, the estimate is (₹12,000 + ₹18,000) ÷ 2 = ₹15,000. More months can make the average less sensitive to one unusual month, but this remains a basic estimate, not a guaranteed forecast. The app groups by months that have completed transactions; it does not fill missing months with zeroes.

### Expense insights

FinTrack groups completed expense transactions by category. A category needs at least three expense records before it is checked for an unusually high value. It calculates the category's average and standard deviation, then uses:

```text
Signal threshold = category average + 2 × standard deviation
```

If the checked expense amount exceeds that threshold, the page flags it for review. A flag is only a statistical signal; it does not prove that the expense is wrong or fraudulent. No flag does not prove that every expense is normal.

### Trends and recommendations

The revenue and expense trend chart is a visual summary of completed transactions by month. High expense categories are ordered by total recorded spend. Recommendations are simple prompts based on whether expenses exceed revenue or whether the anomaly check found a signal. Review the underlying transactions before taking action.

## Search, filters, and lists

Resource pages show up to 20 records per page by default and provide page controls. Search and filters narrow the records before you move between pages. If a list is empty, check that the selected status, category, or date range matches your records and that the transaction status is Completed when you expect it to affect totals.

## Common questions

**Why did a transaction not change Revenue, Expenses, or AI Insights?**  
Those calculations include Completed transactions only. Check the transaction's type, status, amount, and date.

**Why is an invoice still outstanding after I recorded a payment?**  
The payment may be partial. Compare the invoice total with its completed payments. The balance reaches zero only when payments cover the full total.

**Why does the cash-flow estimate say there is not enough data when I have many records?**  
The estimate needs records across at least two different months. Many transactions from a single month are still only one monthly observation. Pending and cancelled records do not count.

**Does “Sent” email the invoice?**  
No. It changes the invoice status only; send or deliver the invoice using your usual process.

**Can I delete an invoice or customer?**  
An invoice cannot be deleted if it has payments, and a customer cannot be deleted if invoices refer to them. These checks protect your financial history.

## Data and account safety

Only sign in through a trusted FinTrack address. Do not share your password or use a shared browser without logging out. Keep invoice, transaction, and payment details accurate: reports and insights reflect the records entered, and are not a substitute for checking bank statements or professional accounting records.
