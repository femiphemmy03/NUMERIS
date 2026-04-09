# NUMERIS — NGX Investment Intelligence Platform

A Django web application that extracts, parses, and serves structured financial
intelligence from NGX PDF filings. Features a public dashboard, admin portal,
user management, and automated PDF extraction.

---

## Quick Start (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run database migrations
python manage.py migrate

# 3. Create your first superadmin account
python manage.py create_superadmin --email you@email.com --password yourpassword

# 4. Start the server
python manage.py runserver
```

Open http://127.0.0.1:8000/

---

## URLs

| URL | Description |
|-----|-------------|
| `/` | Public dashboard — view all companies |
| `/company/MTNN/` | Company detail page |
| `/accounts/login/` | Sign in |
| `/accounts/logout/` | Sign out |
| `/portal/` | Admin portal home |
| `/portal/upload/` | Upload a PDF and auto-extract |
| `/portal/filings/` | Manage all filings |
| `/portal/companies/` | View all companies in DB |
| `/portal/users/` | Manage users |
| `/api/company/MTNN/` | JSON chart data API |

---

## User Roles

| Role | Can Do |
|------|--------|
| **Viewer** | View public dashboard only |
| **Admin** | Upload PDFs, manage filings, create viewer accounts |
| **Super Admin** | Everything — including managing all users and roles |

---

## Adding New Data

### Option A — Upload via Admin Portal (recommended)
1. Go to `/portal/upload/`
2. Drop in the PDF
3. Company is auto-detected from the filename
4. Extraction runs automatically
5. New company appears on dashboard instantly

### Option B — Run extraction script locally
```bash
# Put PDFs in data/raw/
python scripts/auto_extract_basic.py

# Then commit processed files to git for Render deployment
git add data/processed/
git commit -m "Add new filings"
git push
```

---

## Project Structure

```
numeris/
├── manage.py
├── requirements.txt
├── build.sh                    # Render build script
├── render.yaml                 # Render config
│
├── numeris/                    # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── accounts/                   # Auth app
│   ├── models.py               # Custom User model (roles)
│   ├── views.py                # Login, logout, register
│   └── templates/accounts/
│
├── financials/                 # Public dashboard app
│   ├── models.py               # Company, Filing, Metric
│   ├── data_service.py         # File-based data parser
│   ├── views.py                # Dashboard views
│   └── templates/financials/
│
├── admin_panel/                # Admin portal app
│   ├── views.py                # Upload, manage filings/users
│   ├── extractor.py            # PDF → DB extraction engine
│   ├── decorators.py           # admin_required, superadmin_required
│   └── templates/admin_panel/
│
├── data/
│   ├── raw/                    # Drop PDFs here
│   └── processed/              # Extracted .txt and .csv files
│
└── media/
    └── pdfs/                   # PDFs uploaded via admin portal
```

---

## Deploying to Render

1. Push project to GitHub
2. Create new Web Service on Render → connect GitHub repo
3. Set **Build Command**: `./build.sh`
4. Set **Start Command**: `gunicorn numeris.wsgi:application --bind 0.0.0.0:$PORT`
5. Add a **PostgreSQL** database (Render dashboard → New → PostgreSQL)
6. Set environment variables:
   - `SECRET_KEY` — any long random string
   - `DEBUG` — `False`
   - `DATABASE_URL` — auto-set by Render when you attach the DB
7. After first deploy, run in Render Shell:
   ```
   python manage.py create_superadmin --email you@email.com --password yourpassword
   ```
