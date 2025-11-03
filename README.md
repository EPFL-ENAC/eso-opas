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

### Backend

In one shell, run:

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
