from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database
from backend.app.schema.chat import (
    ChatRequest,
    ChatResponse,
    SummarizeRequest,
    SummarizeResponse,
    ChatHistoryInDB,
)
from backend.app.schema.response import ResponseModel
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, sanitize_input
from backend.app.service.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


@router.post("/query", response_model=ChatResponse)
async def chat_query(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    sanitized_query = sanitize_input(request.query)
    request.query = sanitized_query
    chat_service = ChatService(db)
    try:
        response = await chat_service.process_query(
            user_id=current_user["sub"],
            chat_request=request
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )

@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_document(
    request: SummarizeRequest,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    chat_service = ChatService(db)
    try:
        summary = await chat_service.summarize_document(
            user_id=current_user["sub"],
            document_id=request.document_id,
            max_length=request.max_length
        )
        return SummarizeResponse(
            summary=summary,
            document_id=request.document_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to summarize document: {str(e)}"
        )

@router.get("/history", response_model=List[ChatHistoryInDB])
async def get_chat_history(
    session_id: str = None,
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    chat_service = ChatService(db)
    history = await chat_service.get_chat_history(
        user_id=current_user["sub"],
        session_id=session_id,
        limit=limit
    )
    return history

@router.delete("/history/{session_id}", response_model=ResponseModel)
async def delete_chat_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    chat_service = ChatService(db)
    success = await chat_service.delete_chat_session(
        user_id=current_user["sub"],
        session_id=session_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    return ResponseModel(
        success=True,
        message="Chat session deleted successfully"
    )
