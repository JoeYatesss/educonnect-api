FROM python:3.11-slim

WORKDIR /code

# Install system dependencies (libmagic for python-magic)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY ./app /code/app

# Expose port
EXPOSE 8000

# Run application (--proxy-headers ensures HTTPS redirects work behind Railway's proxy)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
