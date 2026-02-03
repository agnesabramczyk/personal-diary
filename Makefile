.PHONY: bootstrap deploy build-push preview destroy lint test dev-up dev-down dev-logs dev-shell dev-rebuild

# Variables
IMAGE_NAME := personal-diary
INFRA_DIR := infrastructure

# Local development targets
dev-up:
	docker-compose up -d
	@echo "Application running at http://localhost:8080"

dev-down:
	docker-compose down

dev-logs:
	docker-compose logs -f app

dev-shell:
	docker-compose exec app /bin/bash

dev-rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo "Application rebuilt and running at http://localhost:8080"

# Cloud infrastructure targets

# First-time setup: create registry, build image, deploy everything
bootstrap:
	@echo "Creating Artifact Registry..."
	cd $(INFRA_DIR) && pulumi up --target '*registry*' --yes
	@echo "Building and pushing initial image..."
	$(MAKE) build-push
	@echo "Deploying full infrastructure..."
	cd $(INFRA_DIR) && pulumi up --yes

# Regular deployment: build, push, update infrastructure
deploy:
	$(MAKE) build-push
	cd $(INFRA_DIR) && pulumi up --config image_tag=$$(git rev-parse --short HEAD)

# Build and push Docker image
build-push:
	@IMAGE_TAG=$$(git rev-parse --short HEAD) && \
	IMAGE_URL=$$(cd $(INFRA_DIR) && pulumi stack output artifact_registry_url)/$(IMAGE_NAME):$$IMAGE_TAG && \
	echo "Building $$IMAGE_URL..." && \
	docker build --platform linux/amd64 -t "$$IMAGE_URL" . && \
	docker push "$$IMAGE_URL"

# Preview changes without applying
preview:
	cd $(INFRA_DIR) && pulumi preview

# Destroy all resources (requires confirmation)
destroy:
	cd $(INFRA_DIR) && pulumi destroy

# Run linting
lint:
	uvx ruff check .
	cd $(INFRA_DIR) && uvx ty check

# Run tests
test:
	pytest tests/
