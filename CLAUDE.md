# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**OPAS** (Open Processing of Airborne imaging Spectrometry) — a web application for processing airborne hyperspectral imagery using TIE (Tie-point Identification and Estimation) detection.

## Common Commands

### Root level
```bash
make install        # Install all dependencies (backend + frontend + pre-commit hooks)
make dev            # Run backend and frontend concurrently
make run-backend    # Backend at http://localhost:8000/docs
make run-frontend   # Frontend at http://localhost:9000
make test           # Run backend tests
make lint           # Lint backend + frontend
```

### Backend (from `backend/`)
```bash
make run                  # Start uvicorn dev server (reads ../.env)
make test                 # Run pytest
make lint                 # Run pre-commit on all files
make build-tie-detector   # Build the TIE detector Docker image
uv run dotenv -f ../.env run pytest tests/test_foo.py::test_bar  # Run a single test
```

### Frontend (from `frontend/`)
```bash
npm run dev     # Dev server
npm run build   # Production build
npm run lint    # ESLint
npm run format  # Prettier
```

## Architecture

### High-level flow
1. User uploads hyperspectral BIL/HDR image pairs via the frontend
2. Backend creates a UUID session and stores files under `UPLOAD_DIR_PATH/{session_id}/`
3. User triggers TIE detection processing; backend creates a Kubernetes Job (`tie-detector`) that mounts the shared PVC for input/output
4. Frontend polls `/process/{session_id}/status` until complete, then displays results

### Backend (`backend/api/`)
FastAPI app with two routers mounted at `/upload` and `/process`:

- **`config.py`** — Pydantic settings loaded from `../.env`. Three settings: `PATH_PREFIX`, `APP_URL`, `UPLOAD_DIR_PATH`.
- **`views/`** — Thin route handlers; delegate all logic to services.
- **`services/upload.py`** — Handles chunked file uploads (5 MB chunks), separates `.bil`/`.hdr` pairs from other files.
- **`services/process.py`** — Orchestrates TIE detection via Kubernetes Jobs (Python `kubernetes` SDK); falls back to Docker SDK when `USE_K8S=false` for local dev.
- **`models/`** — Pydantic request/response models only; no ORM.

### TIE Detector (`backend/tie/`)
A custom Docker image built from C++ sources (steviapp + PikaLTools). Processing parameters (corner detection, RANSAC iterations/threshold, per-image line ranges) are passed via a JSON config file mounted into the container. Input BIL/HDR files go to `/headlessIn`, outputs (PDFs, CSVs) come from `/headlessOut`. Progress is written to `/headlessOut/progress.json` at each step.

In production, this image is published to `ghcr.io/epfl-enac/epfl-eso/opas/tie` and run as a Kubernetes Job. The image is built and pushed **manually** (not via CI), then the digest is pinned in the overlay kustomization:
```bash
cd backend && make push-tie-detector TAG=dev   # builds, pushes, prints digest
# then paste digest into enack8s-app-config/epfl-eso/opas/overlays/dev/kustomization.yaml
```
For local dev without K8s, build the local image:
```bash
cd backend && make build-tie-detector
```

### Frontend (`frontend/src/`)
Quasar (Vue 3) SPA with Pinia stores, Vue Router, and vue-echarts for visualization. `envi_image_reader/` contains a browser-side ENVI format parser. Internationalization via `vue-i18n` (English only currently).

## Environment Setup

Copy or edit `.env` at the repo root. For local dev, `PATH_PREFIX` should be empty:
```
PATH_PREFIX=
USE_K8S=false   # set to true to use K8s jobs (requires kubeconfig or in-cluster)
```

In production, non-secret backend config is injected via the `opas-api-config` ConfigMap in kustomize (see `overlays/*/kustomization.yaml`): `USE_K8S`, `ENVIRONMENT`, `UPLOAD_DIR_PATH`, `TIE_DETECTOR_IMAGE`, `TIE_DETECTOR_IMAGE_TAG`, `TIE_DETECTOR_PVC_NAME`. Actual secrets (API keys etc.) come from Infisical via `opas-api-secrets`.

The backend reads `.env` via `python-dotenv` CLI wrapper in Makefile targets.

## Related Repositories

- `/home/pierre/dev/enack8s-app-config/epfl-eso/opas/` — Kubernetes/ArgoCD deployment config (Kustomize base + dev/prod overlays, PVC, RBAC, Infisical secrets)

## Code Style

Pre-commit hooks enforce:
- **ruff** — linting + import sorting + formatting (line length 120)
- **mypy** — type checking
- **codespell** — typo detection
- **Conventional Commits** — commit message format required
