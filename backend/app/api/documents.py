from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.rate_limit import limiter
from backend.app.core.security import get_current_user, sanitize_input
from backend.app.schema.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
)
from backend.app.schema.response import PaginatedResponse, ResponseModel
from backend.app.service.document_service import DocumentService

router = APIRouter(prefix="/document")


@router.post(
    "/upload",
    response_model=ResponseModel,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(None),
    description: str = Form(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    filename = file.filename or ""
    file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if file_ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "File type not allowed. Allowed types: "
                f"{', '.join(settings.allowed_extensions)}"
            ),
        )

    file_content = await file.read()
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )
    if len(file_content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "File too large. Maximum size: "
                f"{settings.max_upload_size / 1024 / 1024}MB"
            ),
        )

    doc_title = sanitize_input(title) if title else filename
    doc_description = sanitize_input(description) if description else None
    document_data = DocumentCreate(
        title=doc_title,
        file_type=file_ext,
        file_size=len(file_content),
        description=doc_description,
        content="",
    )

    document_service = DocumentService(db)
    document = await document_service.create_document(
        user_id=current_user["sub"],
        document_data=document_data,
        file_content=file_content,
    )

    background_tasks.add_task(
        document_service.process_document,
        document.id,
        current_user["sub"],
    )
    return ResponseModel(
        success=True,
        message="Document accepted for processing",
        data=DocumentResponse(**document.model_dump()),
    )


@router.get("/", response_model=PaginatedResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    skip = max(skip, 0)
    document_service = DocumentService(db)
    documents = await document_service.list_user_documents(
        user_id=current_user["sub"],
        skip=skip,
        limit=limit,
    )
    total = await document_service.count_user_documents(current_user["sub"])
    return PaginatedResponse(
        items=[DocumentResponse(**doc.model_dump()) for doc in documents],
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.post(
    "/{document_id}/reindex",
    response_model=ResponseModel,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("5/minute")
async def reindex_document(
    request: Request,
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    document_service = DocumentService(db)
    document = await document_service.prepare_reindex(
        document_id=document_id,
        user_id=current_user["sub"],
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    background_tasks.add_task(
        document_service.process_document,
        document_id,
        current_user["sub"],
    )
    return ResponseModel(
        success=True,
        message="Document queued for reindexing",
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    document_service = DocumentService(db)
    document = await document_service.get_document(
        document_id=document_id,
        user_id=current_user["sub"],
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return DocumentResponse(**document.model_dump())


@router.patch("/{document_id}")
async def update_document(
    document_id: str,
    update_data: DocumentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    document_service = DocumentService(db)
    document = await document_service.update_document(
        document_id=document_id,
        user_id=current_user["sub"],
        update_data=update_data,
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return ResponseModel(
        success=True,
        message="Document updated successfully",
        data=DocumentResponse(**document.model_dump()),
    )


@router.delete("/{document_id}", response_model=ResponseModel)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    document_service = DocumentService(db)
    success = await document_service.delete_document(
        document_id=document_id,
        user_id=current_user["sub"],
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return ResponseModel(
        success=True,
        message="Document deleted successfully",
    )
