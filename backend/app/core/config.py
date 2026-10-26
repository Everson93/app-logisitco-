from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "LogiCost Intelligence"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://logicost:logicost@localhost:5432/logicost"
    api_prefix: str = "/api/v1"
    # Pasta do frontend compilado. Vazia em desenvolvimento, onde o Vite serve o frontend.
    static_dir: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
