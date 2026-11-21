from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

from backend.app.core.config import settings

security = HTTPBearer()

# bcrypt chỉ xử lý tối đa 72 byte
BCRYPT_MAX_BYTES = 72


class Security:
    @staticmethod
    def get_password_hash(password: str) -> str:
        password_bytes = password.encode("utf-8")[:BCRYPT_MAX_BYTES]
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hash_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES],
                hash_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm,
        )

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm,
        )

    @staticmethod
    def decoded_jwt(token: str) -> dict:
        try:
            return jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
        except PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @staticmethod
    def verify_token_type(payload: dict, expected_type: str) -> bool:
        return payload.get("type") == expected_type


async def get_current_user(
    data: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    payload = Security.decoded_jwt(data.credentials)
    if not Security.verify_token_type(payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("sub") is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def sanitize_input(text: str) -> str:
    """Loại bỏ ký tự điều khiển, giữ nguyên dấu câu/nháy để không làm hỏng nội dung."""
    if not text:
        return ""
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch.isprintable())
    return cleaned.strip()
