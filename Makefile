.PHONY: install dev api web test build docker

install:  ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

dev:  ## Run API (:8000) and web app (:5173) together
	@trap 'kill 0' INT TERM; \
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test:  ## Backend tests + frontend type-check and build
	cd backend && uv run pytest -q
	cd frontend && npm run build

docker:  ## Build and run everything in one container on :8000
	docker compose up --build
