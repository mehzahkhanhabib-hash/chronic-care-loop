# Chronic Care Loop: the four products and the API in one container (no third-party packages)
FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV CCL_WEB=/app CCL_RULES=/app/4-data-model/rules CCL_DB=/data/ccl.db PORT=8000 PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000
WORKDIR /app/server
CMD ["python3", "-m", "backend.server"]
