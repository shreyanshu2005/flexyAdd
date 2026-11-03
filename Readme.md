# Finance Dashboard (flexyAdd)

A personal and small-team finance tracker built with Django REST Framework. Track income and expenses, set budgets, add records in plain language, and **import UPI payments automatically from your Android phone**, including money you lend to friends and get back.

**Live app:** https://flexyadd.onrender.com/app/
**API docs (Swagger):** https://flexyadd.onrender.com/api/docs/

> The app runs on Render's free plan, so it sleeps when idle. The first page load after a quiet period can take up to a minute.

---

## Features

- **Dashboard and analytics**: income, expenses and net balance with change versus the previous period, monthly trend chart, top spending categories, insights and alerts, and a date filter.
- **Records**: add, edit, delete, search and filter. Export to CSV, import from CSV (up to 1000 rows, all-or-nothing). Deleted records are soft-deleted.
- **Quick add in plain language**: type `spent 450 on lunch yesterday` or `got 85k salary on 1 oct`. Amount, type, date and category are detected, and categories are learned from your own history.
- **Budgets**: monthly limit per category, with alerts at 80% and when exceeded.
- **UPI auto-import (Android)**: bank UPI SMS are forwarded by your phone to the app and turned into records automatically. OTPs, failed payments and non-UPI messages are ignored, and the SMS text itself is never stored.
- **Friends ledger**: mark someone as a friend once. Money you lend and money they pay back is tracked per person, kept out of your income and expenses, and shown as who owes whom.
- **Workspaces and roles**: every workspace is fully isolated. Roles are Admin, Analyst and Viewer.
- **Interface**: single-page UI with light and dark mode and a mobile layout. No build step.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework |
| Authentication | JWT (SimpleJWT), role-based access, hashed API key for phone forwarding |
| API docs | drf-spectacular (OpenAPI / Swagger) |
| Filtering | django-filter |
| Database | PostgreSQL (`psycopg` 3). SQLite for quick local use. |
| Server | gunicorn |
| Frontend | One `index.html` with plain JavaScript and CSS, served by Django at `/app/` |
| Packaging and hosting | Docker, Render (web service and PostgreSQL), GitHub |
| Phone side | MacroDroid (or Tasker) on Android |

## Project structure

```text
.
├── backend/
│   ├── config/        settings, URLs, WSGI
│   ├── core/          constants, permissions, pagination, responses, middleware
│   ├── users/         custom user, workspaces, roles, login, signup
│   ├── records/       records, budgets, CSV, quick add, UPI SMS parser and ingest
│   ├── dashboard/     analytics and the friends ledger
│   ├── frontend/      index.html (the web app)
│   └── postman/       Postman collection and environment
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── DEPLOYMENT.md      Docker and Render deployment steps
└── UPI_AUTO_IMPORT.md Phone setup for UPI auto-import
```

The technical reference (data model, every endpoint, design decisions) is in [`backend/README.md`](backend/README.md).

## Quick start

### Use the live app
1. Open https://flexyadd.onrender.com/app/
2. Click **Create a workspace**, enter a name, your email and a password (8+ characters), then log in. You become the admin of your own workspace.

### Run locally (no PostgreSQL needed)
```bash
git clone https://github.com/shreyanshu2005/flexyAdd.git
cd flexyAdd/backend
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
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

Open http://127.0.0.1:8000/app/ for the app and http://127.0.0.1:8000/api/docs/ for Swagger. To use PostgreSQL instead, remove `USE_SQLITE` and set the `POSTGRES_*` variables from `backend/.env.example`.

### Run with Docker
```bash
docker compose up --build
```
Open http://localhost:8000/app/ and log in with `admin@example.com` / `Admin12345` (created on first start). Change this password for anything beyond local use. See [`DEPLOYMENT.md`](DEPLOYMENT.md).

## UPI auto-import

Your Android phone forwards each bank SMS to the app, and payments are added as records automatically.

```text
Bank SMS  ->  MacroDroid on your phone  ->  POST /api/records/ingest/sms/  ->  Record
```

1. Log in as admin, open the **UPI sync** tab, and click **Create key**. Copy it, because it is shown only once.
2. Paste a real bank SMS into **Test an SMS** to see how it will be read. Nothing is saved.
3. In MacroDroid, create a macro with an SMS trigger and an HTTP POST action to `https://<your-app>/api/records/ingest/sms/`, with the header `X-Ingest-Key: <your key>`, content type `text/plain`, and the SMS text as the body.
4. On the **Records** tab, click **Friend** on a payment to or from a friend. From then on, their payments are sorted automatically.

Full steps, limits and the API are in [`UPI_AUTO_IMPORT.md`](UPI_AUTO_IMPORT.md).

## Roles

| Role | Can do |
|---|---|
| **Viewer** | Dashboard and budgets (read only) |
| **Analyst** | Viewer access, plus read and export records |
| **Admin** | Everything: create, edit, delete and import records, manage budgets and users, and UPI sync |

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key. Set a long random value in production. | insecure placeholder |
| `DEBUG` | `1` for development, `0` in production | `0` |
| `ALLOWED_HOSTS` | Comma-separated domains | `*` |
| `USE_SQLITE` | `1` to use SQLite instead of PostgreSQL | `0` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | PostgreSQL connection | localhost values |
| `SETUP_TOKEN` | Enables first-admin setup (only works while no users exist) | unset |
| `ALLOW_REGISTRATION` | `0` turns off public workspace signup | `1` |
| `ACCESS_TOKEN_LIFETIME_MINUTES`, `REFRESH_TOKEN_LIFETIME_DAYS` | JWT lifetimes | `30`, `7` |
| `INGEST_UTC_OFFSET_MINUTES` | Offset used for "today" when an SMS has no date | `330` (India) |

## Testing

```bash
cd backend
python manage.py test
```

The suite has 34 tests covering users and roles, records, dashboard analytics, workspace isolation, the UPI SMS parser (HDFC, SBI, ICICI, Axis and Kotak styles), the ingest endpoint, the friends ledger, and login.

## Deployment

Deployed on **Render** as a Docker web service with a Render PostgreSQL database. Pushing to the `main` branch redeploys automatically, and migrations run on every start. The `POSTGRES_*`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG` and `SETUP_TOKEN` variables must be set on the web service. See [`DEPLOYMENT.md`](DEPLOYMENT.md) for the full steps.

## Security notes

- Passwords are hashed, and login uses short-lived JWTs. Emails are case-insensitive.
- Workspace data is isolated: users, records, budgets, dashboard and exports never cross workspaces.
- The phone's ingest key is stored only as a hash, can be replaced or revoked at any time, and stops working if the admin who created it is deactivated or demoted.
- CSV export neutralises spreadsheet formulas, and requests are rate-limited per endpoint group.
- Use HTTPS in production, and never commit real keys or `.env` files.

## Known limitations

- UPI auto-import works on **Android only**, because iOS does not allow apps to read SMS.
- The SMS parser covers common bank formats. If your bank's message is ignored or misread, use the test box in **UPI sync**, and extend the parser in `backend/records/sms_parser.py`.
- Free Render hosting sleeps when idle, and free databases can expire. Export a CSV backup regularly.

## Documentation

- [`backend/README.md`](backend/README.md): architecture, data model, API reference
- [`UPI_AUTO_IMPORT.md`](UPI_AUTO_IMPORT.md): phone setup and the friends ledger
- [`DEPLOYMENT.md`](DEPLOYMENT.md): Docker and Render
- `backend/postman/`: Postman collection and environment