FROM node:24-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICEFLOW_DATABASE_URL=sqlite:////data/serviceflow.db \
    SERVICEFLOW_FRONTEND_DIR=/app/frontend
WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend \
    && groupadd --system serviceflow \
    && useradd --system --gid serviceflow serviceflow \
    && mkdir -p /data \
    && chown serviceflow:serviceflow /data
COPY --from=frontend /build/frontend/dist ./frontend/
USER serviceflow
EXPOSE 8011
CMD ["python", "-m", "uvicorn", "serviceflow.main:app", "--host", "0.0.0.0", "--port", "8011"]
