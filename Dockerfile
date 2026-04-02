FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Build SQLite database from public-domain IFSC + PIN code datasets
RUN python scripts/build_db.py

# Railway sets PORT dynamically (usually 8080) — app reads it at runtime
# DPDP Act compliance: --no-access-log suppresses request logging
CMD exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log
