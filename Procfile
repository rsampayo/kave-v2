release: python scripts/verify_production_db.py && alembic upgrade head
web: uvicorn app.main:app --host=0.0.0.0 --port=${PORT:-8000}
worker: celery -A app.worker.celery_app worker --loglevel=info
