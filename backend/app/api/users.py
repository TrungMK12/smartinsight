from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.database import get_db
from backend.app.core.security import Security, get_current_user
from backend.app.schema.auth import LoginRequest, RefreshRequest, Token
from backend.app.schema.response import ResponseModel
from backend.app.schema.user import UserCreate, UserResponse
from backend.app.service.user_service import UserService

router = APIRouter(prefix="/user")


@router.post(
    "/register",
    response_model=ResponseModel,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user_data: UserCreate,
    db: AsyncDatabase = Depends(get_db),
):
    user_service = UserService(db)
    try:
        user = await user_service.create_user(user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return ResponseModel(
        success=True,
        message="Created Successfully",
        data=UserResponse(**user.model_dump()),
    )


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def user_login(
    login_data: LoginRequest,
    db: AsyncDatabase = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.auth_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is wrong",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = Security.create_access_token(
        {"sub": user.id, "role": user.role}
    )
    refresh_token = Security.create_refresh_token({"sub": user.id})
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token, status_code=status.HTTP_200_OK)
async def refresh_access_token(
    payload_in: RefreshRequest,
    db: AsyncDatabase = Depends(get_db),
):
    payload = Security.decoded_jwt(payload_in.refresh_token)
    if not Security.verify_token_type(payload, "refresh"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_service = UserService(db)
    user = await user_service.get_user_by_id(payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = Security.create_access_token(
        {"sub": user.id, "role": user.role}
    )
    new_refresh_token = Security.create_refresh_token({"sub": user.id})
    return Token(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
):
    user_service = UserService(db)
    user = await user_service.get_user_by_id(current_user.get("sub"))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(**user.model_dump())
