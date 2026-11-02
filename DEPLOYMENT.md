# Deployment Guide

## Option 1: Docker (recommended)
```bash
docker compose up --build
```
Then open **http://localhost:8000/app/** and log in with `admin@example.com` / `Admin12345`
(created automatically on first start). Override with env vars:
`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SECRET_KEY`, `POSTGRES_PASSWORD`, `SETUP_TOKEN`.
Data persists in the `pgdata` volume; `docker compose down -v` wipes it.

## Option 2: Render
`render.yaml` is included. Create a Render PostgreSQL database and a web service from this repo, then set:

| Variable | Value |
|---|---|
| `DEBUG` | `0` |
| `SECRET_KEY` | long random string |
| `ALLOWED_HOSTS` | your Render domain |
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | from the Render database |
| `SETUP_TOKEN` | a unique secret |
| `ALLOW_REGISTRATION` | `1` (default) lets anyone create a workspace; `0` disables public signup |

Create the first admin by opening `/app/` → "First time? Set up the admin account",
or use the Render shell: `cd backend && python manage.py setup_admin --email you@x.com --password '...'`.

## Production checklist
- `DEBUG=0`, a unique `SECRET_KEY`, and a restrictive `ALLOWED_HOSTS` (not `*`).
- Change `SETUP_TOKEN`, and the default Docker admin password.
- Serve over HTTPS.
- The `/admin/` Django panel has no static files in this setup; the dashboard at `/app/` and Swagger at `/api/docs/` are unaffected.
