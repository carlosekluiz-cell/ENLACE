FROM python:3.12-slim

WORKDIR /app

# System deps for PostGIS, WeasyPrint, and GDAL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libgdal-dev libgeos-dev libproj-dev \
    libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/python
# Copy pipeline and other modules at project root level
COPY ../python /app/python

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "python.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
