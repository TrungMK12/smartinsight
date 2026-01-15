from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / "backend" / ".env"

class Settings(BaseSettings):
    llm_baseurl: str
    llm_modelname: str
    llm_system_prompt: str
    vector_modelname: str
    secret_key: str
    database_url: str
    database_name: str
    collection_name: str
    allow_origins: list[str]

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), case_sensitive=False)

settings = Settings()