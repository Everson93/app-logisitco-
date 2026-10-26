# Imagem única: a API FastAPI também serve o frontend já compilado.
# Build: docker build -t logicost .   (ou docker compose up --build)

# --- 1. Frontend (React + Vite) ---
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. Backend + arquivos estáticos ---
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    STATIC_DIR=/app/static

WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install .
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY scripts /app/scripts
COPY sample-data /app/sample-data
COPY --from=frontend /app/dist /app/static
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# Sem root dentro do contêiner.
RUN useradd --system --uid 10001 --home /app logicost && chmod +x /usr/local/bin/entrypoint.sh
USER logicost

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
