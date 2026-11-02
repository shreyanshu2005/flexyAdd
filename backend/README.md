# Finance Dashboard Backend

Role-based Django REST Framework backend for a finance dashboard platform. The system is structured around a service layer so views stay thin, business rules stay testable, and analytics remain centralized.

## Stack

- Django 5
- Django REST Framework
- PostgreSQL
- JWT authentication via SimpleJWT
- drf-spectacular for OpenAPI / Swagger
- django-filter for filtering and search

## Folder Structure

```text
backend/
├── config/
├── core/
├── users/
├── records/
├── dashboard/
├── manage.py
└── requirements.txt
```

## Architecture

- `core` contains shared constants, permissions, pagination, response formatting, logging middleware, and exception handling.
- `users` owns authentication, custom user modeling, role assignment, and activation controls.
- `records` owns financial record CRUD, filtering, soft delete, and search.
- `dashboard` owns analytics and aggregation logic.
- `config` wires settings, JWT, Swagger, and URL routing.

Business logic lives in services:

- `users/services.py`
- `records/services.py`
- `dashboard/services.py`

## Data Model

### User

- `id`
- `email` unique
- `password` hashed
- `role` one of `ADMIN`, `ANALYST`, `VIEWER`
- `is_active`
- `created_at`

### Record

- `id`
- `user` foreign key to user
- `amount`
- `type` income or expense
- `category`
- `date`
- `note`
- `is_deleted` soft delete flag
- `created_at`

## Why PostgreSQL

PostgreSQL is a better fit than NoSQL here because the data is strongly structured and query-heavy:

- ACID guarantees matter for financial records.
- Relational integrity helps prevent orphaned records.
- Aggregations like monthly trends and category totals are straightforward and efficient.
- Indexes and query planner support make reporting fast and predictable.

Trade-offs:

- Schema changes require migrations.
- It is less flexible than document databases for unstructured payloads.

## Why Django Instead of FastAPI

- Django gives a mature ORM, auth system, admin tooling, and migration workflow out of the box.
- The assignment needs RBAC, relational modeling, and service-oriented organization, which Django supports cleanly.
- DRF pairs naturally with Django for serializers, validation, permissions, throttling, and pagination.

Trade-off:

- FastAPI is lighter and often faster to bootstrap for pure API services, but Django is a stronger fit for a structured backend with built-in auth and data modeling.

## RBAC Matrix

- `Viewer`: dashboard summaries only.
- `Analyst`: dashboard summaries and record reads.
- `Admin`: full CRUD for records, user management, and analytics.

## Indexing Strategy

Indexes are added for the common access patterns:

- `users.email`
- `users.role, users.is_active`
- `records.user, records.date`
- `records.category, records.type`
- `records.is_deleted, records.date`

This supports user lookups, date-range filtering, category filtering, and active-record scans.

## Query Performance Notes

- Record list queries use `select_related("user")` to avoid N+1 queries.
- Dashboard aggregation uses ORM `aggregate`, `annotate`, and `TruncMonth` instead of Python-side loops.
- Dashboard summary now includes period comparison, top spending categories, business insights, and admin-only user breakdowns.
- Pagination uses limit/offset to keep list responses bounded.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:

```env
DEBUG=1
SECRET_KEY=your-secret-key
USE_SQLITE=0   # set to 1 to use SQLite instead of PostgreSQL
ALLOWED_HOSTS=localhost,127.0.0.1
POSTGRES_DB=finance_dashboard
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
ACCESS_TOKEN_LIFETIME_MINUTES=30
REFRESH_TOKEN_LIFETIME_DAYS=7
SETUP_TOKEN=your-super-secret-setup-token-change-in-production
```

4. Start PostgreSQL and create the database.

5. Run migrations:

```bash
python manage.py migrate
```

6. **Initialize admin account** using the setup endpoint (one-time only):

```bash
curl -X POST http://localhost:8000/api/users/setup/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "SecurePassword123",
    "setup_token": "your-super-secret-setup-token-change-in-production"
  }'
```

Alternatively use the management command: `python manage.py setup_admin --email admin@example.com --password SecurePassword123`

> **Note:** The setup endpoint only works when the database is empty. After creating the first admin, it will reject all further setup attempts. This is a security feature to prevent unauthorized admin creation.

7. Run the API server:

```bash
python manage.py runserver
```

### Web dashboard

Open `http://localhost:8000/app/` for the built-in UI.

### Using Postman

1. Import both files from `postman/`:
   - `Finance Dashboard API.postman_collection.json`
   - `Finance Dashboard API.postman_environment.json`

2. In Postman, update the environment variables:
   - `base_url`: Your API URL (default: `http://127.0.0.1:8000`)
   - `setup_token`: The `SETUP_TOKEN` value from your `.env`
   - `admin_email` & `admin_password`: Your desired admin credentials

3. Run the **"Setup (First-time only)"** request in the Auth folder to create the initial admin
4. Then use **"Login"** to get JWT tokens
5. Other endpoints will auto-populate `access_token` for authenticated requests

## API Endpoints

### Auth

- `POST /api/users/setup/` — Initialize first admin (one-time, requires `setup_token`)
- `POST /api/auth/login/` — Login and get JWT tokens
- `POST /api/auth/refresh/` — Refresh access token

### Users

- `GET /api/users/`
- `POST /api/users/`
- `GET /api/users/{id}/`
- `PATCH /api/users/{id}/role/`
- `PATCH /api/users/{id}/status/`

### Records

- `GET /api/records/`
- `POST /api/records/`
- `GET /api/records/{id}/`
- `PUT /api/records/{id}/`
- `PATCH /api/records/{id}/`
- `DELETE /api/records/{id}/`
- `GET /api/records/export/` — CSV download, same filters as the list (analyst/admin)
- `POST /api/records/import/` — body `{"csv": "date,type,category,amount,note\n..."}` (admin, all-or-nothing)

### Workspaces, budgets, quick add
- `POST /api/users/register/` — create a workspace + its first admin (`ALLOW_REGISTRATION=0` disables)
- `GET/POST /api/budgets/`, `DELETE /api/budgets/{id}/` — monthly category budgets (admin writes; all roles read)
- `GET /api/budgets/status/?month=YYYY-MM` — spent vs limit and alert messages
- `POST /api/records/parse/` — body `{"text": "spent 450 on lunch yesterday"}` returns a record suggestion (admin)

### Dashboard

- `GET /api/dashboard/summary/`

### Docs

- `GET /api/schema/`
- `GET /api/docs/`

## Filtering and Search

Records support:

- `category`
- `type`
- `start_date`
- `end_date`
- `search` for note or category
- `limit` and `offset`

Example:

```http
GET /api/records/?category=Salary&start_date=2026-01-01&end_date=2026-01-31&search=bonus&limit=10&offset=0
```

## Response Format

All responses follow a consistent envelope:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

Errors use the same envelope with `success: false`.

## Sample Requests

### Login

```http
POST /api/auth/login/
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "StrongPass123"
}
```

Sample response:

```json
{
  "success": true,
  "data": {
    "refresh": "<refresh-token>",
    "access": "<access-token>",
    "user": {
      "id": 1,
      "email": "admin@example.com",
      "role": "ADMIN",
      "is_active": true,
      "created_at": "2026-04-04T00:00:00Z"
    }
  },
  "error": null
}
```

### Create Record

```http
POST /api/records/
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "amount": "1200.00",
  "type": "income",
  "category": "Salary",
  "date": "2026-01-31",
  "note": "January salary"
}
```

### Dashboard Summary

```http
GET /api/dashboard/summary/?start_date=2026-01-01&end_date=2026-01-31
Authorization: Bearer <access-token>
```

Try these in Postman:

- `Summary - No Filters`
- `Summary - Current Month`
- `Summary - Comparison Window`
- `Comparison`
- `Category Breakdown`
- `Top Spending Categories`
- `Monthly Trends`
- `Insights`
- `Admin User Breakdown`

Swagger also shows query parameter examples for `start_date` and `end_date`, plus a response example for the analytics payload.

Other dashboard routes:

```http
GET /api/dashboard/comparison/
GET /api/dashboard/categories/
GET /api/dashboard/top-spending/
GET /api/dashboard/trends/
GET /api/dashboard/insights/
GET /api/dashboard/users/
```

The dashboard response includes:

- Summary totals for income, expense, net balance, and transaction count
- Period-over-period comparison
- Category breakdown and top spending categories
- Recent transactions and monthly trends
- Insight flags such as expense spikes or concentration in a single category
- Admin-only user-level breakdown

## Validation and Error Handling

- Amount must be greater than zero.
- Invalid transaction types are rejected.
- Date range filters validate `start_date <= end_date`.
- Permissions are enforced before service execution.
- Soft-deleted records are hidden from normal queries.

## Rate Limiting

Scoped throttles are configured for auth, users, records, and dashboard endpoints. This prevents abuse and keeps the API stable under load.

## Logging

A request logging middleware writes method, path, user, status code, and request duration to the application logger.

## Tests

Basic API tests are included for:

- users module
- records module
- dashboard module

Run them with:

```bash
python manage.py test
```

## Trade-off Summary

- PostgreSQL was chosen for relational integrity, ACID behavior, and aggregation support.
- Django was chosen over FastAPI because the project benefits from built-in auth, ORM, admin, migrations, and DRF integrations.
- A service layer was introduced to keep views thin and business rules reusable.
- The design intentionally avoids microservices to keep the system maintainable and assessment-friendly.
