FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run with gunicorn + uvicorn workers for production
# DPDP Act compliance: --access-logfile /dev/null suppresses access logs
# that could capture request metadata. Error logs go to stderr only for
# critical server errors (no request body data is included).
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "/dev/null", "--log-level", "warning"]
