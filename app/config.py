from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Emplea Humboldt - Postulaciones"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    PORT: int = 8002

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "post_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    JWT_SECRET_KEY: str = "cambia-esta-clave-en-produccion"
    JWT_ALGORITHM: str = "HS256"

    # URL interna del microservicio de empleos (para validar vacantes)
    EMPLEOS_SERVICE_URL: str = "http://localhost:8001"

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "emplea-humboldt-docs"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
