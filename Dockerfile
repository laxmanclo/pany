FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY pany/ ./pany/
COPY database/ ./database/

# Create cache directory for models
RUN mkdir -p /app/cache

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "pany.main:app", "--host", "0.0.0.0", "--port", "8000"]
