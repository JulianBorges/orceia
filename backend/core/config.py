from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    API_SECRET_KEY: str
    ALLOWED_ORIGINS: str
    SUPABASE_DATABASE_URL: str
    REDIS_URL: str
    PINECONE_API_KEY: str
    PINECONE_INDEX_NAME: str = "orceia"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
