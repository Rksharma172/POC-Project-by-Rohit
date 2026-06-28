# Use Python 3.11
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Use stable pip settings for Docker build network retries
ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies with retry logic
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

# Copy all project files
COPY . .

# Create necessary folders
RUN mkdir -p documents chroma_db logs templates

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
