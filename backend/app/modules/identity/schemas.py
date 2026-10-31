"""Strict public identity inputs. Passwords are never whitespace-normalized."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Password = Annotated[str, Field(min_length=1, max_length=1024)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Signup(Input):
    name: Name
    email: EmailStr
    password: Password


class Login(Input):
    email: EmailStr
    password: Password


class ResetRequest(Input):
    email: EmailStr


class ResetConfirm(Input):
    token: str = Field(min_length=1, max_length=256)
    new_password: Password


class CreateStaff(Input):
    name: Name
    email: EmailStr
    temporary_password: Password


class CustomerWrite(Input):
    display_name: Name
    email: EmailStr
    company_name: Name | None = None
    billing_address: dict = Field(default_factory=dict)


class CustomerPatch(Input):
    display_name: Name | None = None
    email: EmailStr | None = None
    company_name: Name | None = None
    billing_address: dict | None = None
