from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from .types import Username, Password


class UserCreate(BaseModel):
    username: Username
    password: Password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class LoginRequest(BaseModel):
    username: Annotated[str, StringConstraints(max_length=50)]
    password: Annotated[str, StringConstraints(max_length=128)]
