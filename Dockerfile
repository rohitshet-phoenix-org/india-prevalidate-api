FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Build SQLite database from public-domain IFSC + PIN code datasets
RUN python scripts/build_db.py

EXPOSE 8000

# Diagnostic startup: print env, test import, then start uvicorn
# These echo lines will appear in Railway's deploy logs
CMD echo "=== BOOT ===" && echo "PORT=${PORT:-not_set}" && echo "PWD=$(pwd)" && ls -la data/prevalidate.db && python -c "print('Importing app...'); from app.main import app; print('App OK')" && echo "Starting uvicorn on port ${PORT:-8000}..." && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log
