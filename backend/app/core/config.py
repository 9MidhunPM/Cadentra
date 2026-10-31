"""Environment contract. Secrets are consumed here, never logged."""

import base64
import binascii
import re
from email import policy
from email.errors import HeaderParseError
from email.parser import Parser
from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from email_validator import EmailNotValidError, validate_email
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

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
    dev_tools_enabled: bool = False
    demo_instance: bool = False
    dev_password_hash: str = Field(default="", repr=False)
    dev_grant_cookie_name: str = "cadentra_dev_grant"

    demo_admin_email: str = "admin@example.com"
    demo_admin_password: str = Field(default="", repr=False)

    @field_validator("dev_password_hash", mode="before")
    @classmethod
    def decode_private_hash(cls, value):
        # Avoid Compose treating Argon2's dollar delimiters as env references.
        if isinstance(value, str) and value.startswith("base64:"):
            try:
                value = base64.b64decode(value[7:], validate=True).decode("ascii")
            except (ValueError, UnicodeError, binascii.Error) as error:
                raise ValueError("Invalid encoded developer password hash") from error
            if not value.startswith("$argon2"):
                raise ValueError("An Argon2 developer password hash is required")
        return value

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
            value = () if not value.strip() else tuple(part.strip() for part in value.split(","))
        addresses = []
        for address in value:
            if not isinstance(address, str) or "%" in address:
                raise ValueError("Trusted web proxies must be exact IP literals")
            try:
                addresses.append(str(ip_address(address)))
            except ValueError:
                raise ValueError("Trusted web proxies must be exact IP literals") from None
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
                raise ValueError("Production requires explicit trusted web proxy IP addresses")
            if not self.session_cookie_secure or not self.app_origin.startswith("https://"):
                raise ValueError("Production requires HTTPS origin and secure session cookies")
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise ValueError("Production requires explicit allowed origins")
        return self

    @model_validator(mode="after")
    def resend_security(self):
        if self.smtp_host.casefold() != "smtp.resend.com":
            return self
        if not self.smtp_starttls or self.smtp_port != 587 or self.smtp_user != "resend":
            raise ValueError("Resend requires STARTTLS, port 587 and its SMTP username")
        if self.smtp_password.strip() and (
            self.smtp_password.startswith("REPLACE_")
            or any(ord(char) < 32 or ord(char) == 127 for char in self.smtp_password)
        ):
            raise ValueError("Resend requires a valid private SMTP key when configured")
        if self.smtp_from.strip():
            try:
                if any(ord(char) < 32 or ord(char) == 127 for char in self.smtp_from):
                    raise ValueError
                header = Parser(policy=policy.default).parsestr("From: " + self.smtp_from + "\n\n")[
                    "From"
                ]
                addresses = header.addresses
                if (
                    header.defects
                    or len(addresses) != 1
                    or not addresses[0].username
                    or not addresses[0].domain
                    or "." not in addresses[0].domain
                    or addresses[0].domain.casefold().endswith((".invalid", ".test", ".localhost"))
                ):
                    raise ValueError
                validate_email(addresses[0].addr_spec, check_deliverability=False)
            except (
                ValueError,
                TypeError,
                AttributeError,
                IndexError,
                EmailNotValidError,
                HeaderParseError,
            ):
                raise ValueError(
                    "Resend requires one valid verified-domain sender when configured"
                ) from None

        def canonical_origin(value):
            try:
                parsed = urlsplit(value)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                ):
                    return False
                host = parsed.hostname
                try:
                    host = str(ip_address(host))
                except ValueError:
                    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
                        return False
                    if any(
                        not part or part.startswith("-") or part.endswith("-")
                        for part in host.split(".")
                    ):
                        return False
                if ":" in host:
                    host = "[" + host + "]"
                port = parsed.port
                if port in {80 if parsed.scheme == "http" else 443}:
                    return False
                canonical = parsed.scheme + "://" + host + (f":{port}" if port else "")
                return value == canonical
            except ValueError:
                return False

        if (
            not canonical_origin(self.app_origin)
            or not self.allowed_origins
            or any(not canonical_origin(origin) for origin in self.allowed_origins)
            or self.app_origin not in self.allowed_origins
        ):
            raise ValueError("Resend requires canonical app and allowed origins")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
