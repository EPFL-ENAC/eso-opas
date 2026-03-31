.PHONY: install lint run-backend run-frontend dev test k3d-up k3d-down

install:
	uvx pre-commit install
	cd backend && make install
	cd frontend && npm install
	touch .env

lint:
	cd backend && make lint
	cd frontend && npm run lint && npm run format

run-backend:
	cd backend && make run

run-frontend:
	cd frontend && npm run dev

dev:
	make -j2 run-backend run-frontend

test:
	cd backend && make test

# ---------- Local K8s (k3d) ----------
# Creates a minimal k3d cluster so the backend (running locally) can spawn
# TIE detector K8s jobs.  Usage:
#   make k3d-up          # one-time setup
#   USE_K8S=true make dev # run backend+frontend as usual, jobs go to k3d
#   make k3d-down        # tear down

TIE_IMAGE ?= ghcr.io/epfl-enac/epfl-eso/opas/tie
TIE_TAG ?= v1.0.4

k3d-up:
	mkdir -p /tmp/opas-uploads
	k3d cluster create opas-local \
		--volume /tmp/opas-uploads:/tmp/opas-uploads || true
	docker pull $(TIE_IMAGE):$(TIE_TAG)
	k3d image import $(TIE_IMAGE):$(TIE_TAG) -c opas-local
	kubectl apply -f k8s-local/namespace.yaml
	kubectl apply -f k8s-local/pvc.yaml
	kubectl apply -f k8s-local/rbac.yaml
	@echo ""
	@echo "k3d cluster ready. Run: make dev-k8s"

dev-k8s:
	USE_K8S=true NAMESPACE=opas make dev

k3d-down:
	k3d cluster delete opas-local
