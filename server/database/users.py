# database/users.py
from bson import ObjectId
from database.db import get_collection

users_collection = get_collection("users")

def create_user(user_data):
    """
    Insert a new user document and return its unique ID.
    """
    result = users_collection.insert_one(user_data)
    return result.inserted_id

def get_user(user_id):
    """
    Retrieve a user document by its ObjectId.
    """
    if not isinstance(user_id, ObjectId):
        user_id = ObjectId(user_id)
    return users_collection.find_one({"_id": user_id})

def update_user(user_id, update_fields):
    """
    Update user details.
    """
    if not isinstance(user_id, ObjectId):
        user_id = ObjectId(user_id)
    users_collection.update_one({"_id": user_id}, {"$set": update_fields})
