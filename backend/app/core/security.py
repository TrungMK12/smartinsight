from passlib.context import CryptContext
from datetime import datetime, timedelta
from backend.app.core.config import settings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWTError

security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Security():
    @staticmethod
    def get_password_hash(password: str):
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hash_password: str):
        return pwd_context.verify(plain_password, hash_password)

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encoder = data.copy()
        expire = datetime.utcnow() + timedelta(settings.access_token_expire_minutes)
        to_encoder.update({
            "exp": expire,
            "type": "access"
        })
        encoded_jwt = jwt.encode(
            to_encoder,
            settings.secret_key,
            settings.algorithm
        )
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        to_encoder = data.copy()
        expire = datetime.utcnow() + timedelta(settings.refresh_token_expire_days)
        to_encoder.update({
            "exp": expire,
            "type": "refresh"
        })
        encoded_jwt = jwt.encode(
            to_encoder,
            settings.secret_key,
            settings.algorithm
        )
        return encoded_jwt
    
    @staticmethod
    def decoded_jwt(token: str) -> dict:
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    @staticmethod
    def verify_token_type(payload: dict, expected_type: str) -> bool:
        token_type = payload.get("type")
        return token_type == expected_type
    
async def get_current_user(data: HTTPAuthorizationCredentials = Depends(security)):
    token = data.credentials
    payload = Security.decoded_jwt(token)
    if not Security.verify_token_type(payload, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

def sanitize_input(text: str) -> str:
    dangerous_chars = ["<", ">", "&", '"', "'", "/", "\\"]
    sanitized = text
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, "")
    return sanitized.strip()