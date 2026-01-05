import os
from functools import lru_cache

from pydantic_settings import BaseSettings

TMP_PATH = "/tmp" if os.name != "nt" else os.path.expanduser(r"~\AppData\Local\Temp")


class Config(BaseSettings):
    PATH_PREFIX: str
    APP_URL: str = "https://opas-dev.epfl.ch"
    UPLOAD_DIR_PATH: str = os.path.join(TMP_PATH, "opas-uploads")


@lru_cache()
def get_config():
    return Config()


config = get_config()
