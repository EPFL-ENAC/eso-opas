# OPAS

_Open Processing of Airborne imaging Spectrometry_


## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) Python package and project manager
- npm
- Make


## Deploying locally

Follow these instructions to run locally. First, run:

```bash
make install
```

Then, edit the `.env` file in the root directory of the repository:

```env
PATH_PREFIX=
USE_K8S=false
```

### Backend

TIE detection runs locally via Docker. Build the detector image once before using it:

```bash
cd backend && make build-tie-detector
```

Then start the backend:

```bash
make run-backend
```

The interactive API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### Frontend

In another shell, run:

```bash
make run-frontend
```

The website will be available at [http://localhost:9000](http://localhost:9000).

## Updating the instructions on the website

Download the [original Markdown instructions](https://gitlab.epfl.ch/topo/opastiepointsdetectordocker/-/raw/main/ToolConfiguration.md) and place the file in `backend/tie/`. Then, convert them into the frontend component:

```bash
make generate-instructions-component
```

## Deploying the TIE detector image

Download the [base Dockerfile](https://gitlab.epfl.ch/topo/opastiepointsdetectordocker/-/raw/main/Dockerfile) and place it in `backend/tie/`. Then, patch it by running:

```bash
cd backend && make patch-tie-detector-dockerfile
```

The TIE detector image is built and pushed manually (not by CI):

```bash
cd backend && make push-tie-detector TAG=dev
```

Copy the printed digest and update `overlays/dev/kustomization.yaml` in the [k8s config repo](https://github.com/EPFL-ENAC/enack8s-app-config).
