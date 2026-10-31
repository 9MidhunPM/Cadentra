UV_CACHE_DIR ?= /tmp/cadentra-platform-uv
export UV_CACHE_DIR
UV ?= uv
API_PORT ?= 8001
WEB_PORT ?= 5171
SMOKE_ORIGIN ?= http://127.0.0.1:$(API_PORT)

.PHONY: help dev db-up migrate native-migrate backend-dev frontend-dev worker worker-native seed-demo seed-demo-native smoke test lint sync mail-up outbox outbox-native
help:
	@printf '%s\n' 'make dev: Compose database+migration+API (frontend-dev in another terminal)' 'make sync/backend-dev/native-migrate: native Python against supplied DATABASE_URL' 'make test/lint: backend+pack; frontend checks when integrated' 'make worker: explicit Compose worker (fails until domain services exist)' 'make seed-demo: explicit non-destructive Compose demo seed' 'make mail-up: loopback-only Mailpit capture inbox/SMTP' 'make outbox-native: dispatch one bounded SMTP batch against native database'

sync:
	$(UV) sync --project backend --frozen

dev:
	docker compose up --build api

db-up:
	docker compose up -d --wait db

migrate:
	docker compose run --rm migrate

native-migrate:
	cd backend && $(UV) run --frozen alembic upgrade head

backend-dev:
	$(UV) run --project backend --frozen uvicorn app.main:app --host 127.0.0.1 --port $(API_PORT) --reload

frontend-dev:
	@test -f frontend/package.json || { printf '%s\n' 'Frontend foundation is not integrated yet.'; exit 2; }
	API_PORT=$(API_PORT) npm --prefix frontend run dev -- --host 127.0.0.1 --port $(WEB_PORT)

worker:
	docker compose --profile worker run --rm worker

worker-native:
	$(UV) run --project backend --frozen python -m app.worker

seed-demo:
	docker compose run --rm api python -m app.seed --demo

seed-demo-native:
	$(UV) run --project backend --frozen python -m app.seed --demo

smoke:
	python3 scripts/smoke.py --origin $(SMOKE_ORIGIN)

test:
	@test -n "$$TEST_DATABASE_URL" || { printf '%s\n' 'Set an explicitly disposable PostgreSQL TEST_DATABASE_URL before running the full suite.'; exit 2; }
	python3 scripts/check_pack.py
	$(UV) run --project backend --frozen pytest backend/tests
	@if test -f frontend/package.json; then npm --prefix frontend run test; else printf '%s\n' 'Frontend tests not run: foundation not integrated.'; fi

lint:
	node --check scripts/check_gate_a.mjs
	$(UV) run --project backend --frozen ruff check backend scripts/smoke.py
	@if test -f frontend/package.json; then npm --prefix frontend run lint && npm --prefix frontend run typecheck; else printf '%s\n' 'Frontend checks not run: foundation not integrated.'; fi

mail-up:
	docker compose up -d mailpit

outbox:
	docker compose run --rm api python -m app.core.outbox --once

outbox-native:
	$(UV) run --project backend --frozen python -m app.core.outbox --once
