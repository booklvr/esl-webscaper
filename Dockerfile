FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DASHBOARD_HOST=0.0.0.0 \
    DASHBOARD_PORT=8080

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN if [ -s requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

COPY . .

RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
