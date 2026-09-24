from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

"""Configuracion de la aplicacion, leida desde el archivo .env."""
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # base de datos
    database_url: str = "sqlite:///./futbot.db"
    
    #auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    
    #CORS
    cors_origins_list: list[str] = ["http://localhost:5173"]
    
     # --- Simulacion de partidos ---
    match_tick_rate: int = 15
    friendly_match_duration_seconds: int = 300
    behavior_timeout_seconds: float = 0.05
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion, leyendo el .env una sola vez."""
    return Settings()
