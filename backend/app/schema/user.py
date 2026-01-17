from typing import Optional
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, EmailStr, Field, field_validator

class UserBase(BaseModel):
    username: str = Field(..., min_length=5, max_length=20)
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    role: str = "user"

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validation_password(cls, password: str):
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in password):
            raise ValueError("Password must contain at least one uppercase letter")
        return password
    
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    
class UserInDB(UserBase):
    id: str = Field(alias="_id")
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        
class UserResponse(UserBase):
    id: str = Field(alias="_id")
    created_at: datetime

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}