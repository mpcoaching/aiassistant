logs:
	docker compose logs -f

status:
	docker compose ps

up:
	docker compose -f infrastructure/compose.yml --env-file .env up -d
	docker compose -f platform/compose.yml --env-file .env up -d

down:
	docker compose -f platform/compose.yml --env-file .env down
	docker compose -f infrastructure/compose.yml --env-file .env down

restart-platform:
	docker compose -f platform/compose.yml --env-file .env restart

restart-infrastructure:
	docker compose -f infrastructure/compose.yml --env-file .env restart


infra-up:
	docker compose -f infrastructure/compose.yml --env-file .env up -d

platform-up:
	docker compose -f platform/compose.yml --env-file .env up -d

up: infra-up platform-up

infra-down:
	docker compose -f infrastructure/compose.yml --env-file .env down

platform-down:
	docker compose -f platform/compose.yml --env-file .env down

