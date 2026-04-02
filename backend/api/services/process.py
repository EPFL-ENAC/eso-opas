import json
import logging
import os
from pathlib import Path

from fastapi import HTTPException

from ..config import config
from ..models.process import ProcessRequest, ProcessResponse, ProcessStatusResponse

logger = logging.getLogger("uvicorn.error")

upload_dir_path = Path(config.UPLOAD_DIR_PATH)


# ---------------------------------------------------------------------------
# Kubernetes helpers
# ---------------------------------------------------------------------------


def _load_k8s_config() -> None:
    from kubernetes import config as k8s_config  # type: ignore[import-untyped]

    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()


def _get_namespace() -> str:
    namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    try:
        with open(namespace_file) as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.environ.get("NAMESPACE", "default")


def _argocd_app_name() -> str:
    env = config.ENVIRONMENT
    if env in ("prod", "production"):
        return "opas"
    return f"opas-{env}"


def _k8s_job_name(session_id: str) -> str:
    return f"tie-detector-{session_id[:8]}"


# ---------------------------------------------------------------------------
# K8s job: create
# ---------------------------------------------------------------------------


async def _start_k8s_job(
    session_id: str, request: ProcessRequest, session_dir: Path, output_dir: Path
) -> ProcessResponse:
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]

    _load_k8s_config()
    namespace = _get_namespace()
    job_name = _k8s_job_name(session_id)
    argocd_app = _argocd_app_name()

    annotations = {
        "argocd.argoproj.io/instance": argocd_app,
        "argocd.argoproj.io/sync-options": "Prune=false",
    }

    # Derive subPaths relative to PVC root.
    # UPLOAD_DIR_PATH is e.g. /data/opas-uploads  →  PVC is mounted at /data
    # subPath for input: opas-uploads/{session_id}
    # subPath for output: opas-uploads/{session_id}/output
    pvc_mount_root = Path(config.UPLOAD_DIR_PATH).parent  # /data
    uploads_rel = Path(config.UPLOAD_DIR_PATH).relative_to(pvc_mount_root)  # opas-uploads
    input_sub_path = str(uploads_rel / session_id)
    output_sub_path = str(uploads_rel / session_id / "output")

    container = k8s_client.V1Container(
        name="tie-detector",
        image=f"{config.TIE_DETECTOR_IMAGE}:{config.TIE_DETECTOR_IMAGE_TAG}",
        image_pull_policy="IfNotPresent",
        env=[k8s_client.V1EnvVar(name="PYTHONUNBUFFERED", value="1")],
        resources=k8s_client.V1ResourceRequirements(
            requests={"cpu": "500m", "memory": "2Gi"},
            limits={"cpu": "2", "memory": "4Gi"},
        ),
        volume_mounts=[
            k8s_client.V1VolumeMount(name="data", mount_path="/headlessIn", sub_path=input_sub_path, read_only=True),
            k8s_client.V1VolumeMount(name="data", mount_path="/headlessOut", sub_path=output_sub_path),
        ],
    )

    volumes = [
        k8s_client.V1Volume(
            name="data",
            persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(
                claim_name=config.TIE_DETECTOR_PVC_NAME
            ),
        )
    ]

    pod_spec = k8s_client.V1PodSpec(
        containers=[container],
        volumes=volumes,
        restart_policy="Never",
        service_account_name=config.TIE_DETECTOR_SERVICE_ACCOUNT,
    )

    job_spec = k8s_client.V1JobSpec(
        template=k8s_client.V1PodTemplateSpec(
            metadata=k8s_client.V1ObjectMeta(annotations=annotations),
            spec=pod_spec,
        ),
        backoff_limit=0,
        ttl_seconds_after_finished=86400,
    )

    job = k8s_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_client.V1ObjectMeta(name=job_name, namespace=namespace, annotations=annotations),
        spec=job_spec,
    )

    batch_v1 = k8s_client.BatchV1Api()
    try:
        batch_v1.create_namespaced_job(namespace=namespace, body=job)
    except k8s_client.ApiException as e:
        if e.status == 409:
            raise HTTPException(status_code=409, detail="Processing job already exists for this session")
        raise HTTPException(status_code=500, detail=f"Failed to create K8s job: {e.reason}")

    logger.info(f"Created K8s job {job_name} in namespace {namespace}")
    return ProcessResponse(status="processing", message=f"TIE detection started. Job: {job_name}")


# ---------------------------------------------------------------------------
# K8s job: status
# ---------------------------------------------------------------------------


async def _get_k8s_status(session_id: str, output_dir: Path) -> ProcessStatusResponse:
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]

    _load_k8s_config()
    namespace = _get_namespace()
    job_name = _k8s_job_name(session_id)

    batch_v1 = k8s_client.BatchV1Api()
    try:
        job = batch_v1.read_namespaced_job(name=job_name, namespace=namespace)
    except k8s_client.ApiException as e:
        if e.status == 404:
            # Job was cleaned up (ttl expired) — check for output files
            return _status_from_output_files(output_dir)
        raise HTTPException(status_code=500, detail=f"Failed to read K8s job: {e.reason}")

    conditions = job.status.conditions or []
    progress = _read_progress(output_dir)

    for condition in conditions:
        if condition.type in ("Complete", "SuccessCriteriaMet") and condition.status == "True":
            output_files = [
                f.name for f in output_dir.iterdir() if f.is_file() and f.name not in ("status.json", "progress.json")
            ]
            return ProcessStatusResponse(
                status="completed",
                message="Processing completed",
                output_files=output_files,
                **progress,
            )
        if condition.type in ("Failed", "FailureTarget") and condition.status == "True":
            return ProcessStatusResponse(status="failed", message="Processing failed. Check logs.", **progress)

    return ProcessStatusResponse(status="processing", message="TIE detection is running", **progress)


# ---------------------------------------------------------------------------
# K8s job: logs
# ---------------------------------------------------------------------------


async def _get_k8s_logs(session_id: str) -> dict[str, str]:
    from kubernetes import client as k8s_client  # type: ignore[import-untyped]

    _load_k8s_config()
    namespace = _get_namespace()
    job_name = _k8s_job_name(session_id)

    core_v1 = k8s_client.CoreV1Api()
    pods = core_v1.list_namespaced_pod(namespace=namespace, label_selector=f"job-name={job_name}")

    if not pods.items:
        raise HTTPException(status_code=404, detail="No pod found for this job. Processing may not have started yet.")

    pod = pods.items[0]
    pod_phase = pod.status.phase or "Unknown"

    try:
        logs = core_v1.read_namespaced_pod_log(name=pod.metadata.name, namespace=namespace, tail_lines=100)
    except k8s_client.ApiException as e:
        raise HTTPException(status_code=500, detail=f"Failed to read pod logs: {e.reason}")

    return {"session_id": session_id, "status": pod_phase.lower(), "logs": logs}


# ---------------------------------------------------------------------------
# Docker fallback (local dev)
# ---------------------------------------------------------------------------

TIE_DETECTOR_LOCAL_IMAGE = "tie-detector:latest"


async def _start_docker_job(session_id: str, session_dir: Path, output_dir: Path) -> ProcessResponse:
    import docker  # type: ignore[import-untyped]
    from docker.errors import ContainerError, ImageNotFound

    try:
        client = docker.from_env()
        try:
            client.images.get(TIE_DETECTOR_LOCAL_IMAGE)
        except ImageNotFound:
            raise HTTPException(
                status_code=500,
                detail=f"TIE detector image '{TIE_DETECTOR_LOCAL_IMAGE}' not found. Run: cd backend && make build-tie-detector",
            )

        container = client.containers.run(
            TIE_DETECTOR_LOCAL_IMAGE,
            volumes={
                str(session_dir.absolute()): {"bind": "/headlessIn", "mode": "ro"},
                str(output_dir.absolute()): {"bind": "/headlessOut", "mode": "rw"},
            },
            detach=True,
            remove=False,
            name=f"tie-detector-{session_id}",
        )
        logger.info(f"Started Docker container {container.short_id} for session {session_id}")
        return ProcessResponse(status="processing", message=f"TIE detection started. Container: {container.short_id}")

    except ContainerError as e:
        raise HTTPException(status_code=500, detail=f"Container error: {e.stderr.decode() if e.stderr else str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TIE detection failed: {str(e)}")


async def _get_docker_status(session_id: str, output_dir: Path) -> ProcessStatusResponse:
    import docker  # type: ignore[import-untyped]

    progress = _read_progress(output_dir)
    try:
        client = docker.from_env()
        container = client.containers.get(f"tie-detector-{session_id}")
        if container.status == "running":
            return ProcessStatusResponse(status="processing", message="TIE detection is running", **progress)
        if container.status == "exited":
            exit_code = container.attrs["State"]["ExitCode"]
            container.remove()
            if exit_code != 0:
                return ProcessStatusResponse(
                    status="failed", message=f"Processing failed (exit {exit_code})", **progress
                )
    except docker.errors.NotFound:
        pass
    except Exception as e:
        logger.error(f"Error checking Docker container: {e}")

    return _status_from_output_files(output_dir, progress)


async def _get_docker_logs(session_id: str) -> dict[str, str]:
    import docker  # type: ignore[import-untyped]

    try:
        client = docker.from_env()
        container = client.containers.get(f"tie-detector-{session_id}")
        logs = container.logs(tail=100).decode("utf-8", errors="replace")
        return {"session_id": session_id, "status": container.status, "logs": logs}
    except docker.errors.NotFound:
        raise HTTPException(
            status_code=404, detail="Container not found. Processing may have completed or not started yet."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _read_progress(output_dir: Path) -> dict[str, int | str | None]:
    progress_file = output_dir / "progress.json"
    if progress_file.exists():
        try:
            data = json.loads(progress_file.read_text())
            return {
                "progress_step": data.get("step"),
                "progress_total": data.get("total"),
                "progress_message": data.get("message"),
            }
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read progress file %s: %s", progress_file, exc)
    return {"progress_step": None, "progress_total": None, "progress_message": None}


def _status_from_output_files(output_dir: Path, progress: dict | None = None) -> ProcessStatusResponse:
    if progress is None:
        progress = _read_progress(output_dir)
    if not output_dir.exists():
        return ProcessStatusResponse(status="not_started", message="Processing has not been started for this session")
    output_files = [
        f.name for f in output_dir.iterdir() if f.is_file() and f.name not in ("status.json", "progress.json")
    ]
    if output_files:
        return ProcessStatusResponse(
            status="completed", message="Processing completed", output_files=output_files, **progress
        )
    return ProcessStatusResponse(status="processing", message="Processing in progress, no output files yet", **progress)


def _validate_session(session_id: str) -> tuple[Path, Path]:
    """Validate session exists with required files. Returns (session_dir, output_dir)."""
    session_dir = upload_dir_path / session_id
    output_dir = session_dir / "output"

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    bil_files = list(session_dir.glob("*.bil"))
    if not bil_files:
        raise HTTPException(status_code=400, detail="No .bil files found in session")
    if len(bil_files) < 2:
        raise HTTPException(
            status_code=400, detail=f"Need at least 2 .bil files for TIE detection, found {len(bil_files)}"
        )

    missing_headers = [f.name for f in bil_files if not f.with_suffix(".hdr").exists()]
    if missing_headers:
        raise HTTPException(status_code=400, detail=f"Missing .hdr files for: {', '.join(missing_headers)}")

    return session_dir, output_dir


# ---------------------------------------------------------------------------
# File download
# ---------------------------------------------------------------------------


def get_output_file(session_id: str, filename: str) -> Path:
    """Return the path to an output file, with path traversal protection."""
    output_dir = upload_dir_path / session_id / "output"
    file_path = output_dir / filename

    if not file_path.resolve().is_relative_to(output_dir.resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return file_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def process_ties(request: ProcessRequest) -> ProcessResponse:
    """Run TIE detector on uploaded files."""
    session_id = request.session_id
    session_dir, output_dir = _validate_session(session_id)

    bil_files = list(session_dir.glob("*.bil"))
    logger.info(f"Starting TIE detection for session {session_id} with {len(bil_files)} .bil file(s)")

    output_dir.mkdir(exist_ok=True)

    config_path = session_dir / "config.json"
    if config_path.exists():
        logger.info(f"Using user-provided config.json for session {session_id}")
    else:
        config_data: dict = {
            "cornerMaxNCorners": request.corner_max_n_corners,
            "ransacIterations": request.ransac_iterations,
            "ransacThreshold": request.ransac_threshold,
        }
        if request.lines_starts:
            config_data["linesStarts"] = request.lines_starts
        if request.lines_ends:
            config_data["linesEnds"] = request.lines_ends
        with open(config_path, "w") as f:
            json.dump(config_data, f)

    if config.USE_K8S:
        return await _start_k8s_job(session_id, request, session_dir, output_dir)
    return await _start_docker_job(session_id, session_dir, output_dir)


async def get_process_results(session_id: str) -> ProcessStatusResponse:
    """Get the status and results of TIE detection for a session."""
    session_dir = upload_dir_path / session_id
    output_dir = session_dir / "output"

    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    if not output_dir.exists():
        return ProcessStatusResponse(status="not_started", message="Processing has not been started for this session")

    if config.USE_K8S:
        return await _get_k8s_status(session_id, output_dir)
    return await _get_docker_status(session_id, output_dir)


async def get_container_logs(session_id: str) -> dict[str, str]:
    """Get logs from the processing job/container."""
    if config.USE_K8S:
        return await _get_k8s_logs(session_id)
    return await _get_docker_logs(session_id)
