.PHONY: start stop reset logs rebuild help

help:
	@echo "Device Grant OAuth 2.0 Demo - Available Commands"
	@echo ""
	@echo "  make start      - Start Keycloak + Postgres with docker-compose"
	@echo "  make stop       - Stop running services"
	@echo "  make reset      - Stop services and remove volumes"
	@echo "  make logs       - Tail docker-compose logs"
	@echo "  make rebuild    - Rebuild Docker images"
	@echo ""
	@echo "Once Keycloak is up, run the client (see README.md):"
	@echo "  python main.py"
	@echo ""

start:
	@echo "Starting Keycloak + Postgres..."
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "Services started. Check logs with 'make logs'"

stop:
	@echo "Stopping services..."
	docker-compose stop

reset:
	@echo "Stopping and removing all containers and volumes..."
	docker-compose down -v
	@echo "Reset complete"

logs:
	docker-compose logs -f

rebuild:
	@echo "Rebuilding Docker images..."
	docker-compose build --no-cache
	@echo "Images rebuilt"

	@echo "Images rebuilt"
