from pymongo import AsyncMongoClient
from backend.app.core.config import settings

class Database:
    def __init__(self, url = settings.database_url, db_name = settings.database_name, collection_name = settings.collection_name):
        self.url = url
        self.db_name = db_name
        self.collection_name = collection_name
        self.client: AsyncMongoClient = None
        self.database = None
        self.collection = None

    async def connect(self):
        try:
            self.client = AsyncMongoClient(self.url)
            self.database = self.client.get_database(self.db_name)
            self.collection = self.database.get_collection(self.collection_name)
        except Exception as e:
            raise Exception("Unable to connect to the database due to the following error: ", e)
        
    async def close(self):
        if self.client:
            await self.client.close()

db = Database()
    
