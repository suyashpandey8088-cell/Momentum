from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    app_env: str = 'development'
    database_url: str = f'sqlite:///{ROOT / "data" / "momentum.db"}'
    storage_dir: Path = ROOT / 'data' / 'uploads'
    frontend_url: str = 'http://localhost:3000'
    cookie_secure: bool = False
    enable_demo: bool = True
    embedded_worker: bool = True
    session_days: int = 14
    max_upload_mb: int = 100
    token_encryption_key: str = ''
    openai_api_key: str = ''
    openai_base_url: str = 'https://api.openai.com/v1'
    llm_model: str = 'gpt-4.1-mini'
    embedding_model: str = 'text-embedding-3-small'
    speech_api_key: str = ''
    speech_base_url: str = 'https://api.openai.com/v1'
    speech_model: str = 'whisper-1'
    embedding_api_key: str = ''
    embedding_base_url: str = 'https://api.openai.com/v1'
    redis_url: str = ''
    supabase_url: str = ''
    supabase_service_role_key: str = ''
    supabase_storage_bucket: str = 'momentum-recordings'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    smtp_from: str = 'MOMENTUM <hello@momentum.local>'
    google_client_id: str = ''
    google_client_secret: str = ''
    linear_client_id: str = ''
    linear_client_secret: str = ''
    notion_client_id: str = ''
    notion_client_secret: str = ''
    slack_client_id: str = ''
    slack_client_secret: str = ''
    api_public_url: str = 'http://localhost:3000'

    @property
    def is_production(self) -> bool:
        return self.app_env == 'production'

@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production:
        if not settings.database_url.startswith('postgresql'):
            raise RuntimeError('Production requires PostgreSQL.')
        if not settings.cookie_secure or not settings.token_encryption_key:
            raise RuntimeError('Production requires secure cookies and TOKEN_ENCRYPTION_KEY.')
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
