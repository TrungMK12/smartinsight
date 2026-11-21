from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.database import get_db
from backend.app.core.rate_limit import limiter
from backend.app.core.security import get_current_user, sanitize_input
from backend.app.schema.chat import (
    ChatHistoryInDB,
    ChatRequest,
    ChatResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from backend.app.schema.response import ResponseModel
from backend.app.service.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.post("/query", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat_query(
    request: Request,
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    chat_request.query = sanitize_input(chat_request.query)
    if not chat_request.query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query is empty",
        )

    chat_service = ChatService(db)
    return await chat_service.process_query(
        user_id=current_user["sub"],
        chat_request=chat_request,
    )


@router.post("/summarize", response_model=SummarizeResponse)
@limiter.limit("10/minute")
async def summarize_document(
    request: Request,
    payload: SummarizeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    chat_service = ChatService(db)
    try:
        summary = await chat_service.summarize_document(
            user_id=current_user["sub"],
            document_id=payload.document_id,
            max_length=payload.max_length,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return SummarizeResponse(
        summary=summary,
        document_id=payload.document_id,
    )


@router.get("/history", response_model=List[ChatHistoryInDB])
async def get_chat_history(
    session_id: Optional[str] = None,
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    limit = min(max(limit, 1), 50)
    chat_service = ChatService(db)
    return await chat_service.get_chat_history(
        user_id=current_user["sub"],
        session_id=session_id,
        limit=limit,
    )


@router.delete("/history/{session_id}", response_model=ResponseModel)
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    chat_service = ChatService(db)
    success = await chat_service.delete_chat_session(
        user_id=current_user["sub"],
        session_id=session_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    return ResponseModel(
        success=True,
        message="Chat session deleted successfully",
    )
