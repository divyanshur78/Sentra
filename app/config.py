from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Sentra AI Backend"
    environment: str = "development"
    database_path: str = "./sentra.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
