from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Security():
    @staticmethod
    def get_password_hash(password: str):
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hash_password: str):
        return pwd_context.verify(plain_password, hash_password)
    