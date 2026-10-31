"""Environment contract. Secrets are consumed here, never logged."""

from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_origin: str = "http://localhost:5171"
    allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:5171",)
    trusted_web_proxy_ips: Annotated[tuple[str, ...], NoDecode] = ()
    database_url: str = Field(
        default="postgresql+psycopg://cadentra@localhost:5433/cadentra_platform", repr=False
    )
    test_database_url: str = Field(default="", repr=False)
    business_timezone: str = "Asia/Kolkata"
    business_currency: Literal["INR"] = "INR"
    session_cookie_name: str = "cadentra_session"
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=86400, gt=0)
    reset_token_ttl_seconds: int = Field(default=1800, gt=0)
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, gt=0, le=65535)
    smtp_user: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_from: str = "noreply@example.invalid"
    smtp_starttls: bool = False
    worker_poll_seconds: int = Field(default=30, gt=0)
    worker_batch_size: int = Field(default=100, gt=0, le=1000)
    demo_admin_email: str = "admin@example.com"
    demo_admin_password: str = Field(default="", repr=False)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            return tuple(x.strip().rstrip("/") for x in value.split(",") if x.strip())
        return value

    @field_validator("trusted_web_proxy_ips", mode="before")
    @classmethod
    def exact_proxy_addresses(cls, value):
        if isinstance(value, str):
            value = (
                ()
                if not value.strip()
                else tuple(part.strip() for part in value.split(","))
            )
        addresses = []
        for address in value:
            if not isinstance(address, str) or "%" in address:
                raise ValueError("Trusted web proxies must be exact IP literals")
            try:
                addresses.append(str(ip_address(address)))
            except ValueError:
                raise ValueError(
                    "Trusted web proxies must be exact IP literals"
                ) from None
        return tuple(dict.fromkeys(addresses))

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if make_url(value).drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value

    @field_validator("business_timezone")
    @classmethod
    def known_zone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @model_validator(mode="after")
    def deployment_security(self):
        if self.app_env == "production":
            if not self.trusted_web_proxy_ips:
                raise ValueError(
                    "Production requires explicit trusted web proxy IP addresses"
                )
            if not self.session_cookie_secure or not self.app_origin.startswith("https://"):
                raise ValueError("Production requires HTTPS origin and secure session cookies")
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise ValueError("Production requires explicit allowed origins")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
