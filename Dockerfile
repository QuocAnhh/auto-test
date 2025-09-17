FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r busqa && useradd -r -g busqa busqa

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /app/results /app/static /app/templates && \
    chown -R busqa:busqa /app

# Switch to non-root user
USER busqa

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/api/config || exit 1

# Run gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "web_app_flask:app"] 