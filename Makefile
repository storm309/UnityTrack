.PHONY: help up down test test-backend test-frontend lint lint-backend lint-frontend gen-api

help:
	@echo "UnityTrack Makefile targets:"
	@echo "  make up             - Run docker-compose up with build"
	@echo "  make down           - Stop docker-compose services"
	@echo "  make test           - Run backend and frontend test suites"
	@echo "  make test-backend   - Run pytest in backend"
	@echo "  make test-frontend  - Run vitest in frontend"
	@echo "  make lint           - Run lint and typechecks for backend and frontend"
	@echo "  make lint-backend   - Run ruff and mypy in backend"
	@echo "  make lint-frontend  - Run eslint and tsc in frontend"
	@echo "  make gen-api        - Generate TypeScript client from OpenAPI"

up:
	docker compose up --build

down:
	docker compose down

test: test-backend test-frontend

test-backend:
	cd backend && python -m pytest

test-frontend:
	cd frontend && npm test

lint: lint-backend lint-frontend

lint-backend:
	cd backend && ruff check .
	cd backend && mypy app tests

lint-frontend:
	cd frontend && npm run lint
	cd frontend && npx tsc --noEmit

gen-api:
	cd frontend && npm run gen:api
