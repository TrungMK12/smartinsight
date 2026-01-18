from pydantic import BaseModel, EmailStr
from datetime import datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str  
    exp: datetime
    type: str  


class LoginRequest(BaseModel):
    email: EmailStr
    password: str