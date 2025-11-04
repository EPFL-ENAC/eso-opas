from functools import lru_cache

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    PATH_PREFIX: str
    APP_URL: str = "https://opas-dev.epfl.ch"
    UPLOAD_DIR_PATH: str = "/tmp/opas_uploads"


@lru_cache()
def get_config():
    return Config()


config = get_config()
