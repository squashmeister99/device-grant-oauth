.PHONY: start login refresh logout reset test logs stop rebuild help

help:
	@echo "Device Grant OAuth 2.0 Demo - Available Commands"
	@echo ""
	@echo "  make start      - Start all services with docker-compose"
	@echo "  make stop       - Stop running services"
	@echo "  make login      - Run device authorization flow"
	@echo "  make refresh    - Refresh access token"
	@echo "  make logout     - Revoke tokens and cleanup"
	@echo "  make reset      - Stop services and remove volumes"
	@echo "  make test       - Run pytest suite"
	@echo "  make logs       - Tail docker-compose logs"
	@echo "  make rebuild    - Rebuild Docker images"
	@echo ""

start:
	@echo "Starting services..."
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 5
	@echo "Services started. Check logs with 'make logs'"

stop:
	@echo "Stopping services..."
	docker-compose stop

login:
	@echo "Starting device authorization flow..."
	docker-compose exec device-client python main.py login

refresh:
	@echo "Refreshing access token..."
	docker-compose exec device-client python main.py refresh

logout:
	@echo "Revoking tokens and cleaning up..."
	docker-compose exec device-client python main.py logout

reset:
	@echo "Stopping and removing all containers and volumes..."
	docker-compose down -v
	@echo "Reset complete"

test:
	@echo "Running tests..."
	docker-compose exec device-client pytest -v

logs:
	docker-compose logs -f

rebuild:
	@echo "Rebuilding Docker images..."
	docker-compose build --no-cache
	@echo "Images rebuilt"
