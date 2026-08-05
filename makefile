logs:
	docker compose logs -f

status:
	docker compose ps

up:
	docker compose -f infrastructure/compose.yml --env-file .env up -d
	docker compose -f platform/compose.yml --env-file .env up -d

down:
	docker compose -f infrastructure/compose.yml --env-file .env down
	docker compose -f platform/compose.yml --env-file .env down

restart-platform:
	docker compose -f platform/compose.yml --env-file .env restart

restart-infrastructure:
	docker compose -f infrastructure/compose.yml --env-file .env restart

infra-rebuild:
	docker compose -f infrastructure/compose.yml --env-file .env down
	git pull
	@echo "Clearing Gitea runner cache..."
	@if docker info >/dev/null 2>&1; then \
		docker run --rm -v $$(pwd)/infrastructure/configs/gitea-runner/cache:/cache alpine sh -c 'rm -rf /cache/* /cache/.[!.]* /cache/..?*' 2>/dev/null || true; \
		docker image prune -f 2>/dev/null || true; \
	else \
		echo "Docker not available, skipping cache clear"; \
	fi
	docker compose -f infrastructure/compose.yml --env-file .env up -d --build

infra-up:
	docker compose -f infrastructure/compose.yml --env-file .env up -d

platform-up:
	docker compose -f platform/compose.yml --env-file .env up -d

up: infra-up platform-up

infra-down:
	docker compose -f infrastructure/compose.yml --env-file .env down

platform-down:
	docker compose -f platform/compose.yml --env-file .env down
