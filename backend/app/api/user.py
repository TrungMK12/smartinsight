from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.schema.auth import LoginRequest, Token
from backend.app.schema.response import ResponseModel
from backend.app.schema.user import UserCreate, UserResponse
from backend.app.service.user import UserService
from backend.app.core.database import get_db
from pymongo.asynchronous.database import AsyncDatabase

router = APIRouter(
    prefix="/user"
)   

@router.post("/register", response_model=ResponseModel, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: AsyncDatabase = Depends(get_db)
):
    us = UserService(db)
    try:
        user = await us.create_user(user_data)
        return ResponseModel(
            success=True,
            message="Created Successfully",
            data=UserResponse(**user.model_dump())
        )
    except ValueError as e:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_user(
    login_data: LoginRequest,
    db: AsyncDatabase = Depends(get_db)
):
    us = UserService(db)
    user = await us.authenticate_user(
        login_data.email,
        login_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
