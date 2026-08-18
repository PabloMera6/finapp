"""
Configuración centralizada de la aplicación.
Todos los secretos y parámetros sensibles se leen exclusivamente
de variables de entorno. Nunca se hardcodean credenciales.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Base de datos
    database_url: str = "postgresql://finapp:finapp@localhost:5432/finapp"

    # Autenticación
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_expire_minutes: int = 60 * 12  # 12h
    admin_email: str = "admin@example.com"
    admin_password: str = "changeme123"

    # Cookies
    cookie_name: str = "finapp_session"
    cookie_secure: bool = False  # True en producción (HTTPS)
    cookie_samesite: str = "lax"

    # CORS
    frontend_origin: str = "http://localhost:3000"

    # Uploads
    max_upload_size_mb: int = 10
    allowed_upload_extensions: str = ".csv,.xlsx,.xls"

    # Zona horaria por defecto para informes mensuales
    default_timezone: str = "Europe/Madrid"

    # Entorno
    environment: str = "development"  # development | production


@lru_cache
def get_settings() -> Settings:
    return Settings()
