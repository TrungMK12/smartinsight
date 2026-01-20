from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId

class DocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    file_type: str
    file_size: int
    description: Optional[str] = None

class DocumentCreate(DocumentBase):
    content: str
    metadata: Optional[Dict[str, Any]] = {}

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class DocumentInDB(DocumentBase):
    id: str = Field(alias="_id")
    user_id: str
    content: str
    chunks: List[str] = []
    vector_ids: List[str] = []  
    metadata: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

class DocumentResponse(DocumentBase):
    id: str = Field(alias="_id")
    user_id: str
    created_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}