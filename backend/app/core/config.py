from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / "backend" / ".env"


class Settings(BaseSettings):
    # --- LLM (Ollama) ---
    llm_baseurl: str
    llm_modelname: str
    llm_system_prompt: str
    llm_timeout: int = 60
    llm_temperature: float = 0.3

    # --- Embedding ---
    vector_modelname: str
    # Nếu bỏ trống, dimension sẽ được lấy tự động từ embedding model
    vector_dimension: int | None = None

    # --- Vector store ---
    vector_db_path: str = "backend/data/vectors"

    # --- Database ---
    database_url: str
    database_name: str

    # --- Auth ---
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- CORS ---
    allow_origins: list[str] = ["http://localhost:3000"]

    # --- Upload / chunking ---
    allowed_extensions: list[str] = ["pdf", "docx", "txt", "md"]
    max_upload_size: int = 20 * 1024 * 1024
    upload_dir: str = "backend/data/uploads"
    chunk_size: int = 500
    chunk_overlap: int = 50

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
