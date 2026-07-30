logs:
	docker compose logs -f

status:
	docker compose ps

# DNS setup - ensures Docker daemon uses public DNS for builds
dns-setup:
	@echo "Configuring Docker DNS for builds..."
	sudo mkdir -p /etc/docker
	sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "dns": ["1.1.1.1", "8.8.8.8"],
  "dns-search": ["."]
}
EOF
	sudo systemctl restart docker

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

infra-rebuild:
	$(MAKE) dns-setup
	docker compose -f infrastructure/compose.yml --env-file .env down
	git pull
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