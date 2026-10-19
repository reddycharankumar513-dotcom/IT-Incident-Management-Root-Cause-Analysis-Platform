import os
from typing import Dict, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = "IT Incident Management & RCA Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # SQLite persistence by default
    DATABASE_URL: str = "sqlite:///./incidents.db"

    # Security & Authentication
    AUTH_ENABLED: bool = True
    API_KEY_ADMIN: str = "adm-key-secret-999"
    API_KEY_ENGINEER: str = "eng-key-secret-555"
    API_KEY_VIEWER: str = "view-key-secret-111"

    # Format: username:password:role
    BASIC_AUTH_USERS: str = "admin:admin123:Admin,engineer:engineer123:Engineer,viewer:viewer123:Viewer"

    # Configurable SLA Resolution Targets (in hours)
    SLA_RESOLUTION_CRITICAL_HOURS: float = 4.0
    SLA_RESOLUTION_HIGH_HOURS: float = 8.0
    SLA_RESOLUTION_MEDIUM_HOURS: float = 24.0
    SLA_RESOLUTION_LOW_HOURS: float = 72.0

    # Configurable SLA Response / Acknowledgment Targets (in hours)
    SLA_RESPONSE_CRITICAL_HOURS: float = 0.25
    SLA_RESPONSE_HIGH_HOURS: float = 0.5
    SLA_RESPONSE_MEDIUM_HOURS: float = 2.0
    SLA_RESPONSE_LOW_HOURS: float = 4.0

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_SENSITIVE_DATA_MASKING: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_resolution_sla_hours(self, severity: str) -> float:
        mapping = {
            "Critical": self.SLA_RESOLUTION_CRITICAL_HOURS,
            "High": self.SLA_RESOLUTION_HIGH_HOURS,
            "Medium": self.SLA_RESOLUTION_MEDIUM_HOURS,
            "Low": self.SLA_RESOLUTION_LOW_HOURS,
        }
        return mapping.get(severity, self.SLA_RESOLUTION_MEDIUM_HOURS)

    def get_response_sla_hours(self, severity: str) -> float:
        mapping = {
            "Critical": self.SLA_RESPONSE_CRITICAL_HOURS,
            "High": self.SLA_RESPONSE_HIGH_HOURS,
            "Medium": self.SLA_RESPONSE_MEDIUM_HOURS,
            "Low": self.SLA_RESPONSE_LOW_HOURS,
        }
        return mapping.get(severity, self.SLA_RESPONSE_MEDIUM_HOURS)

    def get_basic_auth_dict(self) -> Dict[str, Dict[str, str]]:
        """Parses username:password:role from BASIC_AUTH_USERS."""
        users = {}
        for entry in self.BASIC_AUTH_USERS.split(","):
            parts = entry.strip().split(":")
            if len(parts) == 3:
                u, p, r = parts
                users[u] = {"password": p, "role": r}
        return users

settings = Settings()
