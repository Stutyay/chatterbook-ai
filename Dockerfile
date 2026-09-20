FROM python:3.12-slim

# Install ALL dependencies (system + build tools)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    curl \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download the fastembed model to prevent timeout on first startup
RUN python -c "import os; from fastembed import TextEmbedding; os.makedirs('/app/model_cache', exist_ok=True); TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2', cache_dir='/app/model_cache')"

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/pdf_storage /app/source_documents

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD sh -c "uvicorn backend_app:app --host 0.0.0.0 --port ${PORT:-8000}"