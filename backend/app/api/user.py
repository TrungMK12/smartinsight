from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.core.security import Security, get_current_user
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
async def user_login(
    login_data: LoginRequest,
    db: AsyncDatabase = Depends(get_db)
):
    us = UserService(db)
    user = await us.auth_user(
        login_data.email,
        login_data.password
    )
    if not user:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is wrong",
            headers={"WWW-Authenticate": "Bearer"}
        )
    access_token = Security.create_access_token({"sub": user.id, "role": user.role})
    refresh_token = Security.create_refresh_token({"sub": user.id})
    return Token(access_token, refresh_token)

@router.post("/refresh", response_model=Token, status_code=status.HTTP_200_OK)
async def refresh_access_token(
    refresh_token: str,
    db: AsyncDatabase = Depends(get_db)
):
    try:
        payload = Security.decoded_jwt(refresh_token)
        if not Security.verify_token_type(payload, "refresh"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        us = UserService(db)
        user = await us.get_user_by_id(payload.get("sub"))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        access_token = Security.create_access_token({"sub": user.id, "role": user.role})
        refresh_token = Security.create_refresh_token({"sub": user.id})
        return Token(access_token, refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}"
        )
    
@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def user_info(
    current_user = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db)
):
    us = UserService(db)
    user_id = current_user.get("sub")
    user = await us.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse(**user.model_dump())


     

