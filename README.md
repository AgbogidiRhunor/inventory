# Inventory Management App

A simple, production-ready Django inventory tracker for a small business.

## Stack
Python, Django, PostgreSQL, Django Templates, vanilla JS, deployed to Vercel with Vercel Blob for product images.

## Local setup
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, BLOB_READ_WRITE_TOKEN
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```
No public registration — create staff users via Django Admin (`/admin/`) or `createsuperuser`.

## Deploying to Vercel
1. Push this repo to GitHub.
2. Import it into Vercel.
3. Set environment variables in the Vercel project (Settings → Environment Variables): `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL` (a Postgres provider — Neon, Supabase, Vercel Postgres all work), `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `BLOB_READ_WRITE_TOKEN` (create a Vercel Blob store under Storage → Blob and copy its token).
4. Vercel builds `api/index.py` (the WSGI entry point) per `vercel.json`; static files are served from `/static`.
5. Run `python manage.py migrate` against the production `DATABASE_URL` once (locally, pointed at prod) to set up tables, then `createsuperuser`.

## Notes
- Images are validated (jpg/png/webp, 3MB max), resized to a 1200px longest side, then uploaded to Vercel Blob — only the URL is stored in Postgres.
- Stock/sale adjustments use `select_for_update` inside a transaction so available quantity and sold quantity never drift out of sync, and neither can go negative.
- The PDF summary is generated in memory on request — nothing is written to disk.
