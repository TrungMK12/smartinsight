from fastapi import APIRouter, Depends


router = APIRouter(
    prefix="/user"
)

@router.post("/register")
def register_user(username: str, password: str):
    pass