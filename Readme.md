# Finance Dashboard Backend API

A production-ready Django REST Framework backend for financial data management with role-based access control, advanced filtering, and comprehensive analytics.

## Quick Start

### Method 1: Test on Hosted Instance (Easiest)

**Using Swagger UI:**
1. Open the hosted backend URL and navigate to `/api/docs/`
2. Open the **Login** endpoint (`/api/auth/login/`) and click **"Try it out"**
3. Enter provided credentials and execute request:
   - Email: `admin@example.com`
   - Password: `(provided on submission)`
4. Copy the `access` token from the login response
5. Click the **"Authorize"** button (top right) and paste: `Bearer <access_token>`
6. Click **Authorize** and then test all protected endpoints

**Using Postman (Pre-configured):**
1. Open Postman → Click **"Import"** → Select files from `postman/` folder:
   - `Finance Dashboard API.postman_collection.json` (all endpoints)
   - `Finance Dashboard API.postman_environment.json` (auth variables)
2. In Postman, select the imported **Environment** from dropdown (top right)
3. Go to **Auth folder** → Click "Login" request
4. Click **"Send"** → JWT tokens should auto-save to environment variables
5. If tokens are not auto-saved, manually copy `access` and `refresh` from response and save them in the selected environment
6. Now test all other endpoints using the saved token values

### Method 2: Run Locally (no PostgreSQL needed)

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
```
Create `backend/.env`:
```env
DEBUG=1
SECRET_KEY=any-random-text
USE_SQLITE=1
SETUP_TOKEN=mysetuptoken123
```
Then:
```bash
python manage.py migrate
python manage.py setup_admin --email admin@example.com --password Admin12345
python manage.py runserver
```
(To use PostgreSQL instead, remove `USE_SQLITE` and set the `POSTGRES_*` variables from `backend/.env.example`.)

**Open in your browser**
- Dashboard UI: http://127.0.0.1:8000/app/
- Swagger API docs: http://127.0.0.1:8000/api/docs/

### Method 3: Docker
```bash
docker compose up --build
```
Open http://localhost:8000/app/ and log in with `admin@example.com` / `Admin12345` (auto-created). See `DEPLOYMENT.md`.

## What's new: multi-tenant workspaces, budgets, smart entry
- **Workspaces (data isolation).** Every user, record and budget belongs to one workspace; nobody can see another workspace's data (records, dashboard, exports, users). Anyone can create their own workspace from the login page (**Create a workspace**, or `POST /api/users/register/`). Set `ALLOW_REGISTRATION=0` to turn public signup off. Existing data is moved into a `Default` workspace by the migration.
- **Categories are normalised.** `salary`, `Salary ` and `SALARY` are stored as one category (first spelling used in the workspace).
- **Budgets and alerts.** Set a monthly limit per category (**Budgets** tab, `/api/budgets/`); you get alerts at 80% and when a budget is exceeded, shown on the dashboard.
- **Quick add in plain language.** Type `spent 450 on lunch yesterday` or `got 85k salary on 1 oct` into the top bar (`POST /api/records/parse/`). Amount, type, date and category are detected; categories are **learned from your own history** (with built-in keywords for new workspaces). You confirm before saving.
- **New UI.** Sidebar layout, light/dark mode (remembers your choice), mobile bottom tab bar.

## Web Dashboard (`/app/`)
A built-in single-page UI served by the backend (no build step, no CORS setup):
- **Login**, plus a first-time admin setup form (uses `SETUP_TOKEN`)
- **Dashboard**: KPIs with change vs. the previous period, insights, line chart (monthly income vs expense), donut chart (top expense categories), recent transactions, date filter
- **Records**: filter, search, pagination; **Export CSV** (analyst/admin, respects current filters); admins can add, edit, delete and **Import CSV** (columns `date,type,category,amount,note`; all-or-nothing, max 1000 rows)
- **Users** (admin): create users, change roles, activate / deactivate

The UI adapts to the logged-in role (Viewer: dashboard; Analyst: + records; Admin: everything).

## Architecture & Key Features

**Modular Design**
- `users/` - Custom user model with email auth & role-based access (Admin, Analyst, Viewer)
- `records/` - Financial records with soft delete, audit trails, and advanced filtering
- `dashboard/` - Analytics with ORM aggregations for performance
- `core/` - Standardized response envelopes, pagination, permissions middleware

**Security & Production-Ready**
- JWT authentication at `/api/auth/login/` and `/api/auth/refresh/`
- **Setup Route** (`POST /api/users/setup/`): Securely bootstrap first admin user with:
  - Setup token validation (one-time initialization)
  - Rate limiting (5 attempts/hour/IP)
  - Audit logging on all setup attempts
- Request validation & standardized error handling
- CORS & security headers configured

**Advanced Filtering**
- Search across records by financial fields
- Filter by date range, category, transaction type
- Optimized query with select_related & prefetch_related

## Testing

**Unit Tests**
```bash
python manage.py test
```

**Coverage**: Users, Records, Dashboard, Permissions, and Edge Cases

## Deployment

Deployed on **Render** with PostgreSQL.

```bash
# Build
pip install -r backend/requirements.txt

# Run
cd backend && gunicorn config.wsgi:application
```

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for Docker and Render steps.

## Notable Implementation Decisions

1. **Setup Route Pattern**: Addresses the chicken-egg problem of no initial admin—uses token-based security and rate limiting instead of hardcoded credentials
2. **Django/DRF Choice**: Batteries-included framework with excellent ORM, built-in permissions, and mature ecosystem for rapid, secure API development
3. **Custom User Model**: Email-based authentication for better UX than username
4. **Soft Delete**: Maintains audit trail without data loss

## Portfolio

Full-stack projects showcasing production architecture:
- **UI + Backend + AI**: Active 3000+ users, 99.9% uptime projects 
- [Portfolio](https://sandeshlavshetty.vercel.app/)

## UPI auto-import

Bank UPI SMS can be forwarded from an Android phone and imported automatically, with a friends ledger for money lent and repaid. See [UPI_AUTO_IMPORT.md](UPI_AUTO_IMPORT.md).
