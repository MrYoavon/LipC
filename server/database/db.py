# database/db.py
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# It's a good practice to use environment variables for configuration.
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "lip-c")

# Create a global client instance
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

def get_collection(collection_name):
    """
    Retrieve a collection by name.
    """
    return db[collection_name]
