logs:
	docker compose logs -f

status:
	docker compose ps

up: infra-up platform-up

down: platform-down infra-down

platform-down:
	docker compose -f platform/compose.yml --env-file .env down

infra-down:
	docker compose -f infrastructure/compose.yml --env-file .env down

restart-platform:
	docker compose -f platform/compose.yml --env-file .env restart

restart-infrastructure:
	docker compose -f infrastructure/compose.yml --env-file .env restart

infra-rebuild:
	docker compose -f infrastructure/compose.yml --env-file .env down
	git pull
	@echo "Fully resetting Gitea runner..."
	@if docker info >/dev/null 2>&1; then \
		docker rm -f infra_gitea_runner 2>/dev/null || true; \
		docker run --rm -v $$(pwd)/infrastructure/configs/gitea-runner/cache:/cache alpine sh -c 'rm -rf /cache/* /cache/.[!.]* /cache/..?*' 2>/dev/null || true; \
		docker image prune -f 2>/dev/null || true; \
	else \
		echo "Docker not available, skipping runner reset"; \
	fi
	docker compose -f infrastructure/compose.yml --env-file .env up -d --build

infra-up:
	docker network create dev-network 2>/dev/null || true
	docker network create live-network 2>/dev/null || true
	docker compose -f infrastructure/compose.yml --env-file .env down 2>/dev/null || true
	-docker ps -a --filter "name=infra_" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true
	docker compose -f infrastructure/compose.yml --env-file .env up -d

platform-up: infra-up
	docker compose -f platform/compose.yml --env-file .env down 2>/dev/null || true
	-docker ps -a --filter "name=platform_" --filter "name=dev_" --filter "name=live_" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true
	docker compose -f platform/compose.yml --env-file .env up -d

REMOTE_HOST := agent99@192.168.1.238
REMOTE_DIR := /home/agent99/projects/aiassistant

remote-infra-up:
	ssh -o StrictHostKeyChecking=accept-new $(REMOTE_HOST) "cd $(REMOTE_DIR) && make infra-up"

remote-platform-up: remote-infra-up
	ssh -o StrictHostKeyChecking=accept-new $(REMOTE_HOST) "cd $(REMOTE_DIR) && make platform-up"

remote-status:
	ssh -o StrictHostKeyChecking=accept-new $(REMOTE_HOST) "cd $(REMOTE_DIR) && make status"

remote-down:
	ssh -o StrictHostKeyChecking=accept-new $(REMOTE_HOST) "cd $(REMOTE_DIR) && make down"
