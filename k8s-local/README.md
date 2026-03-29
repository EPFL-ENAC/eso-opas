# Local K8s Development with k3d

## Overview

Run the backend locally with `uvicorn --reload` (same DX as `make dev`) while TIE detector jobs run as real K8s jobs in a local k3d cluster. Shared storage via host volume mount.

## Prerequisites

```bash
# Install k3d
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
```

## Usage

```bash
make k3d-up      # Create cluster, pull TIE image, apply manifests
make dev-k8s     # Run backend+frontend locally, jobs go to k3d
make k3d-down    # Tear down cluster
```

## How it works

1. **k3d cluster** created with host volume: `/tmp/opas-uploads` mounted into k3d node at same path
2. **Backend runs locally** with `USE_K8S=true` — uses your kubeconfig (auto-configured by k3d) to create jobs
3. **TIE detector image** pulled from GHCR and imported into k3d (no local build needed)
4. **Shared storage**: backend writes uploads to `/tmp/opas-uploads/{session_id}/`, k3d job pod reads from the same dir via hostPath PV/PVC
5. **Frontend** runs locally via `npm run dev`, talks to backend at localhost:8000

## Path alignment

The backend computes PVC subPaths from `UPLOAD_DIR_PATH` (`/tmp/opas-uploads`):
- `pvc_mount_root` = parent = `/tmp`
- `input_sub_path` = `opas-uploads/{session_id}`
- `output_sub_path` = `opas-uploads/{session_id}/output`

The PV hostPath is `/tmp` on the k3d node, which maps to the host's `/tmp` via the k3d volume mount. So the job pod sees the same files the backend wrote locally.

## Manifests

- `namespace.yaml` — `opas` namespace
- `pvc.yaml` — PV (hostPath `/tmp`) + PVC (bound to PV, `ReadWriteMany`)
- `rbac.yaml` — ServiceAccount + Role (jobs CRUD, pods read, pods/log get) + RoleBinding

## Debugging

```bash
# Check job status
kubectl get jobs -n opas

# Check pod status
kubectl get pods -n opas

# Get pod logs
kubectl logs -n opas -l job-name=<job-name>

# Describe job for events/conditions
kubectl describe job <job-name> -n opas

# Check output files
ls /tmp/opas-uploads/<session-id>/output/
```

## Current status (2026-03-27)

- k3d cluster setup works end-to-end
- TIE detector jobs run successfully in k3d
- Frontend shows progress + logs during processing
- TIE detection step (RANSAC matching) is CPU-intensive and can take 5-10+ minutes per pair — this is normal
- Progress tracking: steps are (1) load config, (2) init project, (3..N) TIE detection per pair, (N+1) export CSVs
- The C++ code prints "Detected N corners" early but RANSAC matching continues silently after that

## Pending items

- [ ] Verify full flow completes: job finishes → status flips to "completed" → output files downloadable
- [ ] Frontend log viewer added (collapsible "Show Logs" in step 4) — needs testing
- [ ] Progress fix applied: removed premature "Done" step from `processing.py`, `total_steps` is now `3 + n_pairs` instead of `3 + n_pairs + 1`
- [ ] Docker image size optimization deferred (~2GB image)
