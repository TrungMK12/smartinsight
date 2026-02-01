from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, Field
from datetime import datetime

class ChatMessage(BaseModel):
    role: str 
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    document_ids: Optional[List[str]] = []
    max_docs: int = Field(default=5, ge=1, le=10)

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]] = []
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SummarizeRequest(BaseModel):
    document_id: str
    max_length: int = Field(default=500, ge=100, le=2000)

class SummarizeResponse(BaseModel):
    summary: str
    document_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatHistoryInDB(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    session_id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}