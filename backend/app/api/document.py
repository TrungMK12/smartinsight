from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, sanitize_input
from backend.app.schema.document import DocumentCreate, DocumentResponse, DocumentUpdate
from backend.app.schema.response import PaginatedResponse, ResponseModel
from backend.app.service.document_service import DocumentService
from mini_vector_db.vector_db import MiniVectorBase
from pymongo.asynchronous.database import AsyncDatabase
import os

router = APIRouter(
    prefix="/document"
)

vb = MiniVectorBase()

UPLOAD_DIR = "backend/data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
VECTOR_DIR = "backend/data/vectors"
os.makedirs(VECTOR_DIR, exist_ok=True)

@router.post("/upload", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db)
):
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    file_content = await file.read()
    if len(file_content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
        )
    doc_title = sanitize_input(title) if title else file.filename
    doc_description = sanitize_input(description) if description else None
    document_data = DocumentCreate(
        title=doc_title,
        file_type=file_ext,
        file_size=len(file_content),
        description=doc_description,
        content=""  
    )
    document_service = DocumentService(db)
    try:
        document = await document_service.create_document(
            user_id=current_user["sub"],
            document_data=document_data,
            file_content=file_content
        )
        return ResponseModel(
            success=True,
            message="Document uploaded and processed successfully",
            data=DocumentResponse(**document.model_dump())
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
@router.get("/", response_model=PaginatedResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db)
):
    if limit > 100:
        limit = 100
    document_service = DocumentService(db)
    documents = await document_service.list_user_documents(
        user_id=current_user["sub"],
        skip=skip,
        limit=limit
    )
    total = await document_service.count_user_documents(current_user["sub"])
    return PaginatedResponse(
        items=[DocumentResponse(**doc.model_dump()) for doc in documents],
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit
    )

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db)
):
    document_service = DocumentService(db)
    document = await document_service.get_document(
        document_id=document_id,
        user_id=current_user["sub"]
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return DocumentResponse(**document.model_dump())

@router.patch("/{document_id}")
async def update_document(
    document_id: str,
    update_data: DocumentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db)
):
    document_service = DocumentService(db)
    document = await document_service.update_document(
        document_id=document_id,
        user_id=current_user["sub"],
        update_data=update_data
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return ResponseModel(
        success=True,
        message="Document update successfully",
        data=DocumentResponse(**document.model_dump())
    )