.PHONY: setup dev up down logs web-check web-build api-test infra-test verify config
setup:
	npm --prefix apps/web ci
	cd apps/api && uv sync --locked
dev:
	docker compose -f compose.yaml -f compose.dev.yaml up --build -d --wait
up:
	docker compose up --build -d --wait
down:
	docker compose down
logs:
	docker compose logs --tail=100 -f
web-check:
	npm --prefix apps/web run typecheck
web-build:
	npm --prefix apps/web run build
api-test:
	cd apps/api && uv run --locked pytest
infra-test:
	python3 -m unittest discover -s infra/tests -v
config:
	docker compose config --quiet
	docker compose -f compose.yaml -f compose.dev.yaml config --quiet
verify: web-check web-build api-test infra-test config
