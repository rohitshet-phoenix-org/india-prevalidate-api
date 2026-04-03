FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and data
COPY app/ ./app/
COPY static/ ./static/
COPY scripts/ ./scripts/
COPY data/ ./data/

# Build SQLite database from public-domain datasets
RUN python scripts/build_db.py

# Railway sets PORT dynamically (typically 8080)
CMD exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
