env_path=../.env

REGISTRY := ghcr.io/epfl-enac/epfl-eso/opas
TAG ?= dev

.PHONY: install run test lint build-tie-detector push-tie-detector

install:
	uv venv --allow-existing
	uv pip install -e .[dev]

patch-tie-detector-dockerfile:
	python tie/patch_dockerfile.py

build-tie-detector:
	docker build -t tie-detector:latest -f tie/Dockerfile tie/

push-tie-detector:
	docker build -t $(REGISTRY)/tie:$(TAG) -f tie/Dockerfile tie/
	docker push $(REGISTRY)/tie:$(TAG)
	@echo ""
	@echo "Digest (paste into overlays/dev/kustomization.yaml):"
	@docker inspect --format='{{index .RepoDigests 0}}' $(REGISTRY)/tie:$(TAG) | sed 's/.*@//'

run:
	uv run dotenv -f "$(env_path)" run uvicorn api.main:app --reload

test:
	uv run dotenv -f "$(env_path)" run pytest

lint:
	uvx pre-commit run --all-files
