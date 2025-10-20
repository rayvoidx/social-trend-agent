
# Consumer Trend Analysis Agent - Makefile

ifneq ($(shell which docker-compose 2>/dev/null),)
    DOCKER_COMPOSE := docker-compose
else
    DOCKER_COMPOSE := docker compose
endif

.PHONY: help install build start stop restart logs clean

help:
	@echo "Consumer Trend Analysis Agent - Available Commands:"
	@echo "  make install      - Start the application (first time)"
	@echo "  make build        - Build and start with latest changes"
	@echo "  make start        - Start the application"
	@echo "  make stop         - Stop the application"
	@echo "  make restart      - Restart the application"
	@echo "  make logs         - View application logs"
	@echo "  make clean        - Stop and remove containers"

install:
	@echo "Starting Trend Analysis Agent for the first time..."
	$(DOCKER_COMPOSE) up -d
	@echo "✅ Trend Agent is running at http://localhost:3000"

build:
	@echo "Building and starting Trend Analysis Agent..."
	$(DOCKER_COMPOSE) up -d --build
	@echo "✅ Build complete. Agent is running at http://localhost:3000"

start:
	@echo "Starting Trend Analysis Agent..."
	$(DOCKER_COMPOSE) start
	@echo "✅ Agent is running at http://localhost:3000"

stop:
	@echo "Stopping Trend Analysis Agent..."
	$(DOCKER_COMPOSE) stop
	@echo "✅ Agent stopped"

restart:
	@echo "Restarting Trend Analysis Agent..."
	$(DOCKER_COMPOSE) restart
	@echo "✅ Agent restarted"

logs:
	$(DOCKER_COMPOSE) logs -f

clean:
	@echo "Stopping and removing Trend Analysis Agent..."
	$(DOCKER_COMPOSE) down -v
	@echo "✅ Cleanup complete"

