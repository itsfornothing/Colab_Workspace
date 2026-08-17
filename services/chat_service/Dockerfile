FROM python:3.13-slim

# psycopg[binary] ships pre-compiled wheels — no build-essential needed.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -M -r appuser && mkdir /app && chown -R appuser:appuser /app

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -f /usr/local/lib/python3.13/site-packages/pip/_vendor/bom.cdx.json

COPY --chown=appuser:appuser . /app

USER appuser
EXPOSE 8000
RUN chmod +x /app/entrypoint.prod.sh

CMD ["/app/entrypoint.prod.sh"]
