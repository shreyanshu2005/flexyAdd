# Finance Dashboard Backend

Technical reference for the Django REST Framework backend behind the Finance Dashboard. For an overview, features and quick start, see the [main README](../Readme.md).

**Live app:** https://flexyadd.onrender.com/app/
**Swagger:** https://flexyadd.onrender.com/api/docs/

The code is organised around a service layer, so views stay thin, business rules stay testable, and analytics stay in one place.

## Stack

- Python 3.12, Django 5, Django REST Framework
- PostgreSQL (psycopg 3), with SQLite available for local use
- JWT authentication via SimpleJWT
- drf-spectacular for OpenAPI / Swagger
- django-filter for filtering and search
- gunicorn for serving, Docker and Render for deployment

## Folder structure

```text
backend/
├── config/        settings, URL routing, WSGI
├── core/          constants, permissions, pagination, response envelope, middleware, exceptions
├── users/         custom user, workspaces, roles, login and signup
├── records/       records, budgets, CSV import/export, quick add, UPI SMS parser and ingest
├── dashboard/     analytics and friends ledger
├── frontend/      index.html (single-page UI served at /app/)
├── postman/       Postman collection and environment
├── manage.py
└── requirements.txt
```

## Architecture

- `core` holds shared constants, permissions, pagination, response formatting, request-logging middleware and exception handling.
- `users` owns authentication, the custom user model, workspaces, role assignment and activation.
- `records` owns record CRUD, filtering, soft delete, budgets, CSV, quick add, and the UPI SMS import.
- `dashboard` owns analytics, aggregation and the friends ledger.
- `config` wires settings, JWT, Swagger and URL routing.

Business logic lives in services: `users/services.py`, `records/services.py`, `records/ingest.py`, `dashboard/services.py`.

## Data model

### Workspace
- `id`, `name`. Every user, record, budget and ingest key belongs to exactly one workspace, and data never crosses workspaces.

### User
- `id`, `email` (unique, stored lowercase, login is case-insensitive), `password` (hashed)
- `role`: `ADMIN`, `ANALYST` or `VIEWER`
- `workspace`, `is_active`, `created_at`

### Record
- `id`, `workspace`, `user` (creator)
- `amount` (greater than zero), `type` (`income` or `expense`), `category`, `date`, `note`
- `kind`: `normal`, `lent` (money you paid for a friend) or `repayment` (money a friend paid back)
- `counterparty`: the friend's name or UPI id, required when `kind` is `lent` or `repayment`
- `upi_ref`: UPI reference of an imported payment, unique per workspace so nothing is imported twice
- `is_deleted` (soft delete), `created_at`

Rules enforced by the API: a `lent` record must be an expense, a `repayment` must be income, and both need a counterparty.

### Budget
- `workspace`, `category`, `monthly_limit`, `created_at`. One budget per category per workspace.

### IngestKey
- `workspace`, `user` (the admin who created it), `key_hash`, `prefix`, `created_at`, `last_used_at`. Only a SHA-256 hash is stored, and the plaintext key is shown once.

## Friends ledger

`lent` and `repayment` records are excluded from income, expense, trend, category and budget calculations, so paying for a friend or being repaid does not distort your numbers. Instead, `GET /api/dashboard/friends/` (also included in `/api/dashboard/summary/` as `friends`) returns a balance per person:

```text
balance = total lent - total repaid
positive: they owe you      negative: you owe them
```

Balances are all-time and not affected by date filters. People are grouped case-insensitively by `counterparty`.

## UPI SMS import

```text
POST /api/records/ingest/sms/      header: X-Ingest-Key
```

- Accepts a raw `text/plain` body (easiest for SMS-forwarder apps), JSON `{"message": "...", "received_at": "..."}`, or form data.
- `records/sms_parser.py` reads amount, debit or credit, the other party (UPI id or name), the 12-digit UPI reference and the date. It covers common HDFC, SBI, ICICI, Axis and Kotak formats.
- Anything that is not a completed UPI payment (OTPs, failed or requested payments, mandates, non-UPI messages) is ignored with a reason, and nothing is guessed.
- Responses use status `created`, `duplicate` or `ignored`. The SMS text is never stored or logged, only the outcome.
- A payment to or from someone already marked as a friend is classified automatically as `lent` or `repayment`. Other payments become normal records, categorised from the payee name and your history.
- The date printed in the SMS is used. If there is none, the `received_at` date is used, then today in the offset set by `INGEST_UTC_OFFSET_MINUTES`.
- The key identifies the workspace, and it stops working if the admin who created it is deactivated or demoted.

## Why PostgreSQL

The data is structured and query-heavy:

- ACID guarantees matter for financial records.
- Relational integrity prevents orphaned records, and constraints such as unique UPI references are enforced by the database.
- Aggregations like monthly trends and category totals are straightforward and fast.
- Indexes and the query planner keep reporting predictable.

Trade-off: schema changes need migrations, and it is less flexible than document databases for unstructured data.

## Why Django instead of FastAPI

- A mature ORM, auth system, admin tooling and migration workflow out of the box.
- The project needs role-based access, relational modelling and a service layer, which Django and DRF support cleanly.
- DRF provides serializers, validation, permissions, throttling and pagination.

Trade-off: FastAPI is lighter for pure API services, but Django fits a structured backend with built-in auth and data modelling better.

## Role-based access

| Role | Access |
|---|---|
| `VIEWER` | Dashboard summaries and budget status |
| `ANALYST` | Viewer access, plus reading and exporting records |
| `ADMIN` | Everything: record CRUD and import, budgets, users, quick add, UPI sync |

## Setup

1. Create and activate a virtual environment, then install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file (see `.env.example`):

```env
DEBUG=1
SECRET_KEY=your-secret-key
USE_SQLITE=0                     # set to 1 to use SQLite instead of PostgreSQL
ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=finance_dashboard
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
ACCESS_TOKEN_LIFETIME_MINUTES=30
REFRESH_TOKEN_LIFETIME_DAYS=7
SETUP_TOKEN=your-setup-token
ALLOW_REGISTRATION=1
INGEST_UTC_OFFSET_MINUTES=330
```

3. Run migrations and start the server:

```bash
python manage.py migrate
python manage.py runserver
```

4. Create the first admin, either with the management command:

```bash
python manage.py setup_admin --email admin@example.com --password SecurePassword123
```

or with the one-time setup endpoint:

```bash
curl -X POST http://localhost:8000/api/users/setup/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "SecurePassword123", "setup_token": "your-setup-token"}'
```

> The setup endpoint only works while the database has no users, and it is rate-limited and audit-logged. You can also skip it and use **Create a workspace** in the web app.

The web app is at `http://localhost:8000/app/`.

### Using Postman

1. Import both files from `backend/postman/`.
2. Select the environment and set `base_url` (default `http://127.0.0.1:8000`), `setup_token`, `admin_email` and `admin_password`.
3. Run **Setup (First-time only)** once, then **Login**. Other requests pick up the saved token.

## API endpoints

### Auth
- `POST /api/users/setup/`: create the first admin (one-time, needs `setup_token`)
- `POST /api/users/register/`: create a workspace and its first admin (`ALLOW_REGISTRATION=0` disables)
- `POST /api/auth/login/`: get JWT tokens
- `POST /api/auth/refresh/`: refresh the access token

### Users (admin)
- `GET /api/users/`, `POST /api/users/`, `GET /api/users/{id}/`
- `PATCH /api/users/{id}/role/`, `PATCH /api/users/{id}/status/`

### Records
- `GET /api/records/`, `POST /api/records/`
- `GET /api/records/{id}/`, `PUT`, `PATCH`, `DELETE /api/records/{id}/`
- `GET /api/records/export/`: CSV with the same filters as the list (analyst and admin)
- `POST /api/records/import/`: body `{"csv": "date,type,category,amount,note\n..."}` (admin, all-or-nothing, up to 1000 rows). Optional `kind` and `counterparty` columns are supported.
- `POST /api/records/parse/`: body `{"text": "spent 450 on lunch yesterday"}` returns a record suggestion (admin)

### UPI import
- `POST /api/records/ingest/sms/`: import one SMS (`X-Ingest-Key` header)
- `POST /api/records/ingest/preview/`: dry-run parse, nothing saved (admin)
- `GET`, `POST`, `DELETE /api/records/ingest/key/`: key status, create or replace, revoke (admin)

### Budgets
- `GET /api/budgets/`, `POST /api/budgets/`, `DELETE /api/budgets/{id}/` (admin writes, all roles read)
- `GET /api/budgets/status/?month=YYYY-MM`: spent versus limit, with alert messages

### Dashboard
- `GET /api/dashboard/summary/`
- `GET /api/dashboard/comparison/`, `/categories/`, `/top-spending/`, `/trends/`, `/insights/`, `/users/`
- `GET /api/dashboard/friends/`: friends ledger

### Docs and health
- `GET /api/docs/` (Swagger), `GET /api/schema/` (OpenAPI), `GET /health/`

## Filtering and search

Records support `category`, `type`, `start_date`, `end_date`, `search` (note or category), `limit` and `offset`.

```http
GET /api/records/?category=Salary&start_date=2026-01-01&end_date=2026-01-31&search=bonus&limit=10&offset=0
```

## Response format

```json
{ "success": true, "data": {}, "error": null }
```

Errors use the same envelope with `success: false`. The one exception is `POST /api/auth/login/`, which returns `refresh`, `access` and `user` directly at the top level.

## Sample requests

### Login
```http
POST /api/auth/login/
Content-Type: application/json

{ "email": "admin@example.com", "password": "StrongPass123" }
```

### Create a record
```http
POST /api/records/
Authorization: Bearer <access-token>
Content-Type: application/json

{ "amount": "1200.00", "type": "income", "category": "Salary", "date": "2026-01-31", "note": "January salary" }
```

### Record money lent to a friend
```http
POST /api/records/
Authorization: Bearer <access-token>
Content-Type: application/json

{ "amount": "500.00", "type": "expense", "category": "Friends", "date": "2026-11-03", "kind": "lent", "counterparty": "rahul@okaxis" }
```

### Import an SMS (as the phone does)
```bash
curl -X POST https://flexyadd.onrender.com/api/records/ingest/sms/ \
  -H "X-Ingest-Key: <your key>" -H "Content-Type: text/plain" \
  --data-binary "Sent Rs.250.00 from Kotak Bank AC X1234 to swiggy@okicici on 03-11-26.UPI Ref 312345678901"
```

### Dashboard summary
```http
GET /api/dashboard/summary/?start_date=2026-01-01&end_date=2026-01-31
Authorization: Bearer <access-token>
```

The summary includes totals, period-over-period comparison, category breakdown, top spending, recent transactions, monthly trends, insight flags, the friends ledger, and (for admins) a per-user breakdown.

## Validation and error handling

- Amounts must be greater than zero.
- Transaction types and record kinds are validated, and friend records must be consistent (type, counterparty).
- Date filters validate `start_date <= end_date`.
- Permissions are enforced before services run.
- Soft-deleted records are hidden from normal queries and are not re-imported by UPI sync.
- Categories are normalised, so `salary`, `Salary ` and `SALARY` become one category.

## Indexing

- Users: `email`, `role + is_active`
- Records: `user + date`, `category + type`, `is_deleted + date`, `workspace + date`, `workspace + kind + counterparty`
- Constraints: `amount > 0`, and a unique `upi_ref` per workspace when set
- Budgets: unique per `workspace + category`

## Performance notes

- Record lists use `select_related("user")` to avoid N+1 queries.
- Dashboard analytics use ORM `aggregate`, `annotate` and `TruncMonth` rather than Python loops.
- Pagination uses limit and offset to keep responses bounded.

## Rate limiting

Scoped throttles apply to auth, users, records, dashboard and ingest endpoints. The ingest scope has its own limit so a phone can send a burst of messages.

## Logging

Request middleware logs method, path, user, status and duration. The ingest endpoint logs only the outcome of each SMS (`created`, `duplicate` or `ignored`, with the reason), never its content.

## Tests

```bash
python manage.py test
```

34 tests cover users and roles, records, CSV, workspace isolation, budgets, quick add, dashboard analytics, the UPI SMS parser, the ingest endpoint, the friends ledger, and login.

## Trade-off summary

- PostgreSQL for relational integrity, ACID behaviour and aggregation support.
- Django over FastAPI for built-in auth, ORM, admin, migrations and DRF integration.
- A service layer keeps views thin and business rules reusable.
- A rule-based SMS parser instead of machine learning, so behaviour is predictable and unrecognised messages are skipped rather than guessed.
- A monolith instead of microservices, to keep the system simple to run and maintain.