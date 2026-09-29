FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN DJANGO_SECRET_KEY=build-only \
    POSTGRES_DB=durc \
    POSTGRES_USER=durc \
    POSTGRES_PASSWORD=build-only \
    python manage.py collectstatic --noinput

RUN useradd --uid 1000 --create-home appuser \
    && mkdir -p /app/data/durc /app/media \
    && chown -R appuser:appuser /app/data/durc /app/media

USER appuser

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
