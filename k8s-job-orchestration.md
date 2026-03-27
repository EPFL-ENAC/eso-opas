# Kubernetes Job Orchestration in AddLidar

This document describes how AddLidar runs processing jobs on Kubernetes using Docker images. It is intended as a reference for implementing similar job orchestration in other projects on EPFL ENACIT4R infrastructure.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Docker Image Access](#docker-image-access)
3. [Starting Jobs (Python)](#starting-jobs-python)
4. [Job Types](#job-types)
   - [On-demand Jobs (Python API)](#on-demand-jobs-python-api)
   - [Batch Jobs (Scanner CronJob)](#batch-jobs-scanner-cronjob)
5. [Indexed Batch Job Pattern](#indexed-batch-job-pattern)
6. [Node Scheduling (RCP-HAAS)](#node-scheduling-rcp-haas)
7. [ArgoCD Integration](#argocd-integration)
8. [Job Monitoring](#job-monitoring)
   - [Real-time WebSocket Updates](#real-time-websocket-updates)
   - [Pod Log Collector](#pod-log-collector)
9. [Job Completion Callbacks](#job-completion-callbacks)
10. [Kubernetes RBAC Requirements](#kubernetes-rbac-requirements)
11. [Key Configuration Variables](#key-configuration-variables)
12. [Key Files Reference](#key-files-reference)

---

## Architecture Overview

Two distinct job creation paths coexist:

```
User Request (HTTP)
    └── POST /start-job/
            └── create_k8s_job()                  # on-demand, Python k8s client
                    └── K8s Job (1 pod)
                            └── reports back via curl → internal API (port 8001)

CronJob (daily 8pm)
    └── scanner.py
            └── queue_batch_zip_job()             # batch, Jinja2 template + k8s client
            └── queue_potree_conversion_jobs()
                    └── K8s Indexed Job (N pods)
                            └── each pod reports back via curl → internal API (port 8001)
```

The backend exposes **two servers simultaneously** from `src/main.py`:
- **Public** (port 8000): User-facing — auth required (Keycloak JWT)
- **Internal** (port 8001): Cluster-only — no auth, for pod callbacks via `curl`

---

## Docker Image Access

### Image References

Images are pulled from container registries configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_NAME` | `lvjospinepfl/lidardatamanager` | On-demand job image |
| `IMAGE_TAG` | `latest` | On-demand job tag |
| `COMPRESSION_IMAGE_REGISTRY` | `ghcr.io` | Registry for batch compression image |
| `COMPRESSION_IMAGE_NAME` | `epfl-enac/epfl-eso/addlidar/compression` | Compression image name |
| `COMPRESSION_IMAGE_TAG` | *(required)* | Compression image tag |
| `COMPRESSION_IMAGE_SHA256` | *(optional)* | Pin to exact digest for reproducibility |
| `POTREE_CONVERTER_IMAGE_REGISTRY` | `ghcr.io` | Registry for Potree converter image |
| `POTREE_CONVERTER_IMAGE_NAME` | `epfl-enac/epfl-eso/addlidar/potree-converter` | Potree image name |
| `POTREE_CONVERTER_IMAGE_TAG` | *(required)* | Potree image tag |

Full image reference format (when SHA256 is provided):
```
ghcr.io/epfl-enac/epfl-eso/addlidar/compression:v1.2.3@sha256:abc123...
```

### Image Pull Policy

- `IfNotPresent` in Jinja2 batch job templates
- No explicit `imagePullSecrets` in job specs — relies on cluster-wide pull secret configuration or public images

Init containers use the standard `docker.io/library/bash:5.1` public image.

---

## Starting Jobs (Python)

### Python Kubernetes Client Setup

The backend uses the official `kubernetes` Python package. In-cluster authentication is automatic:

```python
from kubernetes import client, config, watch

# Loads credentials from service account mounted at:
# /var/run/secrets/kubernetes.io/serviceaccount/
config.load_incluster_config()

batch_v1 = client.BatchV1Api()
core_v1 = client.CoreV1Api()
```

For local development, fall back to kubeconfig:
```python
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()
```

### Reading Current Namespace

```python
def get_current_namespace() -> str:
    namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    try:
        with open(namespace_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get("NAMESPACE", "default")
```

### Creating a Job Object (Python API)

```python
from kubernetes import client

def generate_k8s_job(job_name, image, command, namespace, pvc_name, output_pvc_name):
    annotations = {
        "argocd.argoproj.io/instance": "addlidar-dev",   # Must match ArgoCD app name
        "argocd.argoproj.io/sync-options": "Prune=false", # CRITICAL: prevents ArgoCD deletion
    }

    container = client.V1Container(
        name="worker",
        image=image,
        command=command,
        env=[
            client.V1EnvVar(name="PYTHONUNBUFFERED", value="1"),
        ],
        resources=client.V1ResourceRequirements(
            requests={"cpu": "500m", "memory": "2Gi"},
            limits={"cpu": "2", "memory": "8Gi"},
        ),
        volume_mounts=[
            client.V1VolumeMount(name="data", mount_path="/data", sub_path="fts-addlidar/LiDAR"),
            client.V1VolumeMount(name="output", mount_path="/output"),
        ],
    )

    volumes = [
        client.V1Volume(
            name="data",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=pvc_name),
        ),
        client.V1Volume(
            name="output",
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=output_pvc_name),
        ),
    ]

    node_scheduling = get_node_scheduling_config(namespace)  # tolerations + nodeSelector

    pod_spec = client.V1PodSpec(
        containers=[container],
        volumes=volumes,
        restart_policy="Never",
        tolerations=node_scheduling.get("tolerations"),
        node_selector=node_scheduling.get("node_selector"),
    )

    job_spec = client.V1JobSpec(
        template=client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(annotations=annotations),
            spec=pod_spec,
        ),
        backoff_limit=3,
        ttl_seconds_after_finished=86400,  # Auto-delete after 24h
    )

    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name, annotations=annotations),
        spec=job_spec,
    )

# Create the job
batch_v1.create_namespaced_job(namespace=namespace, body=job_object)
```

---

## Job Types

### On-demand Jobs (Python API)

- Triggered by user via `POST /start-job/`
- One Job = one Pod
- Job name: `job-{uuid4}`
- Monitored in real-time via WebSocket `/ws/job-status/{job_name}`
- Auto-deleted after reaching terminal state
- Status tracked in memory (dict of `JobStatus` objects)

### Batch Jobs (Scanner CronJob)

- Triggered by scanner CronJob (daily at 8pm)
- Scanner scans NAS directories, computes SHA256 fingerprints to detect changes
- Creates **Indexed Batch Jobs** for all changed/new items
- One Job = N pods (one per work item), running in parallel
- No real-time WebSocket — completion reported via callback to internal API
- Status tracked in SQLite database

---

## Indexed Batch Job Pattern

For processing N independent items in parallel, AddLidar uses Kubernetes [Indexed Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/#completion-mode):

```yaml
spec:
  completions: {{ folders | length }}
  parallelism: {{ folders | length }}
  completionMode: Indexed
  template:
    spec:
      initContainers:
        - name: select-work-item
          image: docker.io/library/bash:5.1
          command: ["/bin/bash", "-c"]
          args:
            - |
              FOLDERS=(
              {% for folder, fingerprint in folders %}
                "{{ folder }}|{{ fingerprint }}"
              {% endfor %}
              )
              SELECTED="${FOLDERS[$JOB_COMPLETION_INDEX]}"
              FOLDER=$(echo "$SELECTED" | cut -d'|' -f1)
              FINGERPRINT=$(echo "$SELECTED" | cut -d'|' -f2)
              echo -n "$FOLDER" > /data/input_path.txt
              echo -n "$FINGERPRINT" > /data/fingerprint.txt
          volumeMounts:
            - name: shared-data
              mountPath: /data

      containers:
        - name: worker
          image: "{{ image_registry }}/{{ image_name }}:{{ image_tag }}"
          command: ["/bin/bash", "-c"]
          args:
            - |
              INPUT=$(cat /data/input_path.txt)
              FINGERPRINT=$(cat /data/fingerprint.txt)
              # ... do work ...
              # Report back to backend on success
              curl -X PUT "${BACKEND_URL}/sqlite/folder_state/${INPUT}" \
                --max-time 30 --retry 3 \
                -H "Content-Type: application/json" \
                -d '{"processing_status": "success", "fingerprint": "'"$FINGERPRINT"'"}'
          volumeMounts:
            - name: shared-data
              mountPath: /data
            - name: lidar-data
              mountPath: /lidar-data

      volumes:
        - name: shared-data
          emptyDir: {}
        - name: lidar-data
          persistentVolumeClaim:
            claimName: "{{ fts_addlidar_pvc_name }}"
```

**Key insight**: The work item list is **baked into the job spec** by Jinja2 at creation time. Each pod uses `$JOB_COMPLETION_INDEX` (0, 1, 2, ...) to select its item from the array.

### Using Jinja2 Templates for Job Creation

```python
from jinja2 import Environment, FileSystemLoader
from kubernetes import utils as k8s_utils

env = Environment(loader=FileSystemLoader("templates/"))
template = env.get_template("job-batch.template.yaml")

rendered_yaml = template.render(
    timestamp="20240327120000",
    folders=[("folder1", "sha256abc"), ("folder2", "sha256def")],
    fts_addlidar_pvc_name="lidar-data-pvc",
    backend_url="http://backend-internal:8001",
    image_registry="ghcr.io",
    image_name="myorg/myimage",
    image_tag="v1.0.0",
    tolerations=[{"key": "dedicated", "value": "rcpHAAS", ...}],
    node_selector={"rcpnas3": "available"},
)

import yaml
job_dict = yaml.safe_load(rendered_yaml)

# Add ArgoCD annotations programmatically
job_dict["metadata"]["annotations"].update({
    "argocd.argoproj.io/instance": "myapp-prod",
    "argocd.argoproj.io/sync-options": "Prune=false",
})

# Create the job
k8s_utils.create_from_dict(k8s_client, job_dict, namespace=namespace)
```

---

## Node Scheduling (RCP-HAAS)

EPFL RCP provides high-memory/GPU nodes with taints. Jobs must declare tolerations and node selectors to be scheduled on them.

```python
def get_node_scheduling_config(namespace: str) -> dict:
    """Returns tolerations and node_selector for RCP-HAAS production nodes."""
    if namespace == "epfl-eso-addlidar-prod":
        return {
            "tolerations": [
                client.V1Toleration(
                    key="dedicated",
                    value="rcpHAAS",
                    operator="Equal",
                    effect="NoExecute",
                )
            ],
            "node_selector": {"rcpnas3": "available"},
        }
    return {"tolerations": None, "node_selector": None}
```

In Jinja2 templates (YAML syntax):
```yaml
spec:
  template:
    spec:
      {% if tolerations %}
      tolerations:
        {% for toleration in tolerations %}
        - key: "{{ toleration.key }}"
          value: "{{ toleration.value }}"
          operator: "{{ toleration.operator }}"
          effect: "{{ toleration.effect }}"
        {% endfor %}
      {% endif %}
      {% if node_selector %}
      nodeSelector:
        {% for key, value in node_selector.items() %}
        {{ key }}: "{{ value }}"
        {% endfor %}
      {% endif %}
```

---

## ArgoCD Integration

**This is critical.** When ArgoCD manages a namespace, it will **delete any resource it doesn't know about** during a sync. Dynamically created jobs must carry special annotations:

```python
annotations = {
    # Must match the ArgoCD Application name for this namespace
    # e.g. "addlidar-dev" for epfl-eso-addlidar-dev namespace
    "argocd.argoproj.io/instance": app_name,

    # Prevents ArgoCD from pruning this job during sync
    "argocd.argoproj.io/sync-options": "Prune=false",
}
```

Apply to **both** the Job metadata and the Pod template metadata.

The `app_name` is derived from the environment:
```python
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
app_name = f"addlidar-{ENVIRONMENT}"  # "addlidar-development" or "addlidar-production"
```

---

## Job Monitoring

### Real-time WebSocket Updates

For on-demand jobs, a background thread watches the job and streams updates to the user via WebSocket.

**Thread pattern**:
```python
import threading
from kubernetes import watch

def watch_job_status_thread(job_name, namespace, websocket_notify_fn):
    w = watch.Watch()
    batch_v1 = client.BatchV1Api()

    for event in w.stream(
        batch_v1.list_namespaced_job,
        namespace=namespace,
        field_selector=f"metadata.name={job_name}",
        timeout_seconds=3600,
    ):
        job = event["object"]
        conditions = job.status.conditions or []

        for condition in conditions:
            if condition.type in ("Complete", "SuccessCriteriaMet") and condition.status == "True":
                websocket_notify_fn(job_name, "Complete")
                w.stop()
                # Auto-delete job
                batch_v1.delete_namespaced_job(job_name, namespace,
                    body=client.V1DeleteOptions(propagation_policy="Foreground"))
                return

            if condition.type in ("Failed", "FailureTarget") and condition.status == "True":
                websocket_notify_fn(job_name, "Failed")
                w.stop()
                return
```

**Pod log streaming** (runs in parallel with job watcher):
```python
def stream_pod_logs(job_name, namespace, notify_fn):
    core_v1 = client.CoreV1Api()

    while True:
        pods = core_v1.list_namespaced_pod(
            namespace, label_selector=f"job-name={job_name}"
        )
        if not pods.items:
            time.sleep(2)
            continue

        pod = pods.items[0]
        if pod.status.phase not in ("Running", "Succeeded", "Failed"):
            time.sleep(2)
            continue

        try:
            logs = core_v1.read_namespaced_pod_log(
                pod.metadata.name, namespace, tail_lines=100
            )
            notify_fn(job_name, logs)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                break  # Pod gone
        time.sleep(2)
```

**Sending from thread to asyncio WebSocket**:
```python
import asyncio

async def notify_websocket(job_name: str, status: dict):
    if job_name in active_connections:
        await active_connections[job_name].send_json(status)

def notify_from_thread(job_name: str, status: dict):
    # Bridge from sync thread to async event loop
    asyncio.run_coroutine_threadsafe(
        notify_websocket(job_name, status),
        loop=asyncio_event_loop,
    )
```

### Pod Log Collector

A background service (`PodLogCollector`) captures logs from **all** job pods before they disappear:

```python
class PodLogCollector:
    """Watches pods labeled 'addlidar.io/job-type' and saves logs on failure."""

    def start(self, namespace: str):
        self._thread = threading.Thread(target=self._watch_pods, daemon=True)
        self._thread.start()

    def _watch_pods(self):
        w = watch.Watch()
        for event in w.stream(
            core_v1.list_namespaced_pod,
            self.namespace,
            label_selector="addlidar.io/job-type",
        ):
            pod = event["object"]
            event_type = event["type"]  # ADDED, MODIFIED, DELETED

            should_capture = (
                pod.status.phase in ("Failed", "Succeeded")
                or event_type == "DELETED"
                or any(
                    cs.state.waiting and cs.state.waiting.reason
                    in ("CrashLoopBackOff", "ErrImagePull")
                    for cs in (pod.status.container_statuses or [])
                )
            )

            if should_capture:
                self._save_logs(pod)

    def _save_logs(self, pod):
        log_path = f"/data/pod-logs/{pod.metadata.name}_{timestamp}.log"
        logs = core_v1.read_namespaced_pod_log(pod.metadata.name, self.namespace)
        with open(log_path, "w") as f:
            f.write(logs)
```

Start at application startup:
```python
# In FastAPI lifespan
pod_log_collector = PodLogCollector()
pod_log_collector.start(namespace=get_current_namespace())
```

---

## Job Completion Callbacks

Batch job pods report their completion status to the backend's **internal API** (port 8001) via `curl`:

```bash
# Success
curl -X PUT "${BACKEND_INTERNAL_URL}/sqlite/folder_state/${FOLDER_KEY}" \
  --max-time 30 \
  --retry 3 \
  --retry-delay 5 \
  -H "Content-Type: application/json" \
  -d '{
    "fingerprint": "'"$FINGERPRINT"'",
    "processing_status": "success",
    "processing_time": '"$ELAPSED_SECONDS"'
  }'

# Failure
curl -X PUT "${BACKEND_INTERNAL_URL}/sqlite/folder_state/${FOLDER_KEY}" \
  --max-time 30 \
  --retry 3 \
  -H "Content-Type: application/json" \
  -d '{
    "fingerprint": "'"$FINGERPRINT"'",
    "processing_status": "failed",
    "error_message": "short error",
    "detailed_error_message": "'"$FULL_ERROR"'"
  }'
```

The internal API endpoint (FastAPI, no auth):
```python
@router.put("/sqlite/folder_state/{folder_key}")
async def update_folder_state(folder_key: str, payload: FolderStateUpdate):
    # Update SQLite record
    db.update_folder_state(folder_key, payload)
    return {"status": "ok"}
```

This pattern decouples job completion tracking from Kubernetes job status — even if the Job object is deleted, the completion was already recorded.

---

## Kubernetes RBAC Requirements

The service account running the backend pod needs the following permissions:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: job-manager
rules:
  # Create and manage jobs
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "watch", "delete", "patch"]

  # Read pod status and logs
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]

  # Read events (for debugging)
  - apiGroups: [""]
    resources: ["events"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: job-manager-binding
subjects:
  - kind: ServiceAccount
    name: default  # Or a dedicated service account
roleRef:
  kind: Role
  name: job-manager
  apiGroup: rbac.authorization.k8s.io
```

The scanner CronJob needs the same permissions in its namespace.

---

## Key Configuration Variables

```bash
# Image configuration
IMAGE_NAME=lvjospinepfl/lidardatamanager
IMAGE_TAG=latest
COMPRESSION_IMAGE_REGISTRY=ghcr.io
COMPRESSION_IMAGE_NAME=epfl-enac/epfl-eso/addlidar/compression
COMPRESSION_IMAGE_TAG=v1.0.0
COMPRESSION_IMAGE_SHA256=          # Optional: pin to exact digest

# Kubernetes
NAMESPACE=epfl-eso-addlidar-dev    # Auto-detected from service account if unset
PVC_NAME=lidar-data-pvc
PVC_OUTPUT_NAME=lidar-data-output-pvc

# Backend URLs (for job pods to call back)
BACKEND_INTERNAL_URL=http://backend-internal:8001

# ArgoCD
ENVIRONMENT=development            # Maps to ArgoCD app: "addlidar-development"

# Resource limits (configurable)
CPU_REQUEST=500m
CPU_LIMIT=2
MEMORY_REQUEST=2Gi
MEMORY_LIMIT=8Gi
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `backend/lidar-api/src/services/k8s_addlidarmanager.py` | On-demand job creation, K8s API calls, job watching, log streaming |
| `backend/lidar-api/src/utils/kubernetes_utils.py` | Namespace detection, RCP-HAAS scheduling config |
| `scanner/lib/kubernetes_utils.py` | Scanner copy of kubernetes utils (keep in sync!) |
| `backend/lidar-api/src/config/settings.py` | All environment variable definitions |
| `backend/lidar-api/src/services/pod_log_collector.py` | Background pod log capture service |
| `backend/lidar-api/src/api/routes.py` | WebSocket endpoint `/ws/job-status/{job_name}` |
| `backend/lidar-api/src/api/sqlite/folder_state.py` | Internal API for job completion callbacks |
| `scanner/scanner.py` | Scanner CronJob entrypoint, batch job creation |
| `scanner/lib/scanner.py` | Directory scanning, fingerprinting, change detection |
| `scanner/job-batch-compression.template.yaml` | Jinja2 template: indexed batch compression jobs |
| `scanner/job-batch-potree-converter.template.yaml` | Jinja2 template: indexed batch Potree jobs |
| `scanner/lib/api_client.py` | HTTP client for scanner → backend internal API |

---

## Summary: Checklist for a New Project

When creating a similar system on EPFL ENACIT4R Kubernetes:

- [ ] Use `kubernetes` Python package with `load_incluster_config()`
- [ ] Read namespace from `/var/run/secrets/kubernetes.io/serviceaccount/namespace`
- [ ] Add ArgoCD annotations `argocd.argoproj.io/instance` and `sync-options: Prune=false` to all dynamically created jobs
- [ ] Ensure ArgoCD app name matches your namespace convention
- [ ] Add RCP-HAAS tolerations for production (`dedicated=rcpHAAS`) and node selector (`rcpnas3=available`)
- [ ] Set `ttl_seconds_after_finished` on jobs for automatic cleanup
- [ ] Use `backoff_limit=3` for retry behavior
- [ ] Deploy internal API (no auth) for job pods to report completion via `curl`
- [ ] Implement `PodLogCollector` background service to capture logs before pod deletion
- [ ] Configure RBAC: `batch/jobs` CRUD + `pods` read + `pods/log` get
- [ ] For N parallel items: use `completionMode: Indexed` with initContainer to distribute work
- [ ] Bake work item list into Jinja2 templates at job creation time
- [ ] Mount PVCs at consistent paths (configure via env vars, not hardcoded)
- [ ] Set `PYTHONUNBUFFERED=1` for real-time log streaming
