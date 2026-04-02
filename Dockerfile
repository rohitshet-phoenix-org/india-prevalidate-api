FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Build SQLite database from public-domain IFSC + PIN code datasets
# (~60s download + build, cached in Docker layer)
RUN python scripts/build_db.py

# Railway injects $PORT at runtime — do not hardcode
EXPOSE ${PORT:-8000}

# Run with gunicorn + uvicorn workers
# - 1 worker to stay within Railway free-tier memory (512 MB)
# - log-level info so Railway deploy logs show startup/binding
# - access-logfile /dev/null: DPDP Act compliance (no request logging)
CMD ["sh", "-c", "exec gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout 120 --access-logfile /dev/null --log-level info"]
