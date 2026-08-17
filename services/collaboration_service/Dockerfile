FROM python:3.13-slim

# Install only the runtime library needed by psycopg[binary].
# psycopg[binary] ships pre-compiled wheels so we do NOT need
# build-essential or libpq-dev — that was the cause of the
# "cannot allocate memory" build failure (344 MB of compiler
# toolchain was being downloaded and compiled inside Docker).
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

# Install Python dependencies as root so they land in the system site-packages
# (accessible to appuser at runtime).
COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . /app

USER appuser
EXPOSE 8000
RUN chmod +x /app/entrypoint.prod.sh

CMD ["/app/entrypoint.prod.sh"]
