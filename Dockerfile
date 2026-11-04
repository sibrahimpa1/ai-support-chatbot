# Stage 1: build the React frontend
FROM node:22-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python API that also serves the built frontend
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
# Bake the embedding model into the image so containers start offline.
RUN .venv/bin/python -c "from app.config import Settings; from app.embeddings import load_embedder; s = Settings(); assert load_embedder(s.embedding_model, str(s.model_cache_dir))"
COPY --from=web /app/frontend/dist /app/frontend/dist
ENV PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
