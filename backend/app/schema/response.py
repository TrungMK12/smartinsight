from typing import Any, List, Optional
from pydantic import BaseModel

class ResponseModel(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None

class ResponseError(BaseModel):
    detail: str 
    error_code: Optional[str]

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

