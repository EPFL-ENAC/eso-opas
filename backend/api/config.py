import os
from functools import lru_cache

from pydantic_settings import BaseSettings

TMP_PATH = "/tmp" if os.name != "nt" else os.path.expanduser(r"~\AppData\Local\Temp")


class Config(BaseSettings):
    PATH_PREFIX: str = ""
    APP_URL: str = "https://opas-dev.epfl.ch"
    UPLOAD_DIR_PATH: str = os.path.join(TMP_PATH, "opas-uploads")
    # K8s job orchestration
    USE_K8S: bool = False
    ENVIRONMENT: str = "development"  # "dev" or "prod" — drives ArgoCD annotation
    TIE_DETECTOR_IMAGE: str = "ghcr.io/epfl-enac/epfl-eso/opas/tie"
    TIE_DETECTOR_IMAGE_TAG: str = "latest"
    TIE_DETECTOR_PVC_NAME: str = "opas-pvc"  # "opas-pvc-dev" in dev namespace


@lru_cache()
def get_config():
    return Config()


config = get_config()
