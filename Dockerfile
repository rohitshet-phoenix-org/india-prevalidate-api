FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Build SQLite database from public-domain IFSC + PIN code datasets
RUN python scripts/build_db.py

# Railway injects $PORT at runtime
EXPOSE 8000

# Use uvicorn directly — simpler, lighter, reliable $PORT expansion
# DPDP Act compliance: --no-access-log suppresses request logging
CMD python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log
