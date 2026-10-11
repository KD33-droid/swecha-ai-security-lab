from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://swecha:swecha_dev@localhost:5432/swecha_lab"
    )
    redis_url: str = "redis://localhost:6379/0"
    environment: str = "development"
    organizer_auth_secret: str = ""
    organizer_username: str = ""
    organizer_password_hash: str = ""
    ta_username: str = ""
    ta_password_hash: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+psycopg://" + value[len("postgres://"):]
            if value.startswith("postgresql://"):
                return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
