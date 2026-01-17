from typing import Optional
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.core.config import settings

class Database:
    def __init__(self):
        self.client: Optional[AsyncMongoClient] = None
        self.database: Optional[AsyncDatabase] = None

    async def connect(self):
        try:
            self.client = AsyncMongoClient(settings.database_url)
            self.database = self.client.get_database(settings.database_name)
        except Exception as e:
            raise Exception("Unable to connect to the database due to the following error: ", e)
        
    async def close(self):
        if self.client:
            await self.client.close()

    def get_database(self):
        if self.database is None:
            raise Exception("Database connection is not established.")
        return self.database

db = Database()

async def get_db():
    return db.get_database()    
