FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose API and Streamlit ports
EXPOSE 8000 8501

ENV APP_ENV=production
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
