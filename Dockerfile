# ---- Base image with Python 3.11 (stable wheels for pandas/numpy) ----
FROM python:3.11-slim

# ---- System setup ----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Optional: speed up pip a bit
ENV PIP_NO_CACHE_DIR=1

# ---- Workdir ----
WORKDIR /app

# ---- Install dependencies ----
# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy app code ----
COPY . .

# ---- Port & startup ----
ENV PORT=8080
EXPOSE 8080

# Run the Dash app via Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "fraud_dashboard:app.server"]
