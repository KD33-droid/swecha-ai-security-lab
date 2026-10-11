import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.organizer_auth import (
    TOKEN_LIFETIME,
    create_token,
    verify_password,
)

router = APIRouter(prefix="/organizer/auth", tags=["organizer-auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    accounts = (
        (
            "organizer",
            settings.organizer_username,
            settings.organizer_password_hash,
        ),
        (
            "ta",
            settings.ta_username,
            settings.ta_password_hash,
        ),
    )

    for role, configured_username, password_hash in accounts:
        if (
            configured_username
            and password_hash
            and hmac.compare_digest(request.username, configured_username)
            and verify_password(request.password, password_hash)
        ):
            return LoginResponse(
                access_token=create_token(role),
                role=role,
                expires_in=TOKEN_LIFETIME,
            )

    raise HTTPException(status_code=401, detail="Invalid username or password")
