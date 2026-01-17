from typing import Optional
from bson import ObjectId
from backend.app.schema.user import UserCreate, UserInDB, UserUpdate
from backend.app.core.security import Security
from datetime import datetime
from pymongo import ReturnDocument


class UserService:
    def __init__(self,db):
        self.db = db
        self.collection = self.db.get_collection("users")

    async def create_user(self, user_data: UserCreate) -> UserInDB:
        existing_user = await self.collection.find_one({
            "$or" : [
                {"email": user_data.email},
                {"username": user_data.username}
            ]
        })
        if existing_user:
            raise ValueError("User already exist")
        hash_password = Security.get_password_hash(user_data.password)
        user_dict = user_data.model_dump(exclude={"password"})
        user_dict.update({
            "hashed_password": hash_password,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })  
        results = await self.collection.insert_one(user_dict)
        user_dict["_id"] = str(results.inserted_id)
        return UserInDB(**user_dict)
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        user = await self.collection.find_one({"email": email})
        if user:
            user["_id"] = str(user["_id"])
            return UserInDB(**user)
        return None
    
    async def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        user = await self.collection.find_one({"username": username})
        if user:
            user["_id"] = str(user["_id"])
            return UserInDB(**user)
        return None
    
    async def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[UserInDB]:
        if not ObjectId.is_valid(user_id):
            return None
        update_data = user_data.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = Security.get_password_hash(
                update_data.pop("password")
            )
        update_data["updated_at"] = datetime.utcnow()
        result = await self.collection.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        if result:
            result["_id"] = str(result["_id"])
            return UserInDB(**result)
        return None
    
    async def auth_user(self, password: str, username: str = None, email: str = None) -> Optional[UserInDB]:
        if not username and not email:
            return None
        if username and email:
            return None  
        if username:
            user = await self.get_user_by_username(username)
        if email:
            user = await self.get_user_by_email(email)
        if not user:
            return None
        if not Security.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    