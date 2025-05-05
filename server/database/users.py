# database/users.py
"""
User database access utilities.

This module provides CRUD operations for user documents in MongoDB,
including creating users, retrieving by ID or username, and managing contacts.
"""
from bson import ObjectId
from pymongo import ReturnDocument
from database.db import get_collection

# MongoDB collection for user documents
users_collection = get_collection("users")


async def create_user(user_data: dict) -> ObjectId:
    """
    Insert a new user record into the database.

    Args:
        user_data (dict): Dictionary containing user fields:
            - username (str)
            - password_hash (str)
            - name (str)
            - contacts (list of ObjectId, empty by default)

    Returns:
        ObjectId: The MongoDB-generated _id of the new user document.

    Raises:
        PyMongoError: If insertion into the collection fails.
    """
    result = await users_collection.insert_one(user_data)
    return result.inserted_id


async def get_user_by_id(user_id: str | ObjectId) -> dict | None:
    """
    Retrieve a user document by its unique identifier.

    Args:
        user_id (str or ObjectId): The user's ObjectId or its string representation.

    Returns:
        dict or None: The user document if found; otherwise None.
    """
    if not isinstance(user_id, ObjectId):
        user_id = ObjectId(user_id)
    return await users_collection.find_one({"_id": user_id})


async def get_user_by_username(username: str) -> dict | None:
    """
    Retrieve a user document by its username.

    Args:
        username (str): The username to search for.

    Returns:
        dict or None: The user document if found; otherwise None.
    """
    return await users_collection.find_one({"username": username})


async def add_contact_to_user(user_id: str | ObjectId, contact_username: str) -> dict | None:
    """
    Add another user as a contact to the given user's contact list.

    Uses MongoDB's $addToSet to prevent duplicates.

    Args:
        user_id (str or ObjectId): The owner's user ID.
        contact_username (str): The username of the contact to add.

    Returns:
        dict or None: The updated user document after adding the contact,
                      or None if the contact username does not exist.
    """
    contact = await get_user_by_username(contact_username)
    if not contact:
        return None
    contact_id = contact.get("_id")
    updated = await users_collection.find_one_and_update(
        {"_id": ObjectId(user_id) if not isinstance(
            user_id, ObjectId) else user_id},
        {"$addToSet": {"contacts": contact_id}},
        return_document=ReturnDocument.AFTER
    )
    return updated


async def get_user_contacts(user_id: str | ObjectId) -> list[dict]:
    """
    Fetch full contact records for a user's contact list.

    Args:
        user_id (str or ObjectId): The user whose contacts to retrieve.

    Returns:
        list of dict: List of user documents for each contact,
                      with _id and any nested contact IDs stringified.
    """
    user = await get_user_by_id(user_id)
    if not user or not user.get("contacts"):
        return []
    contact_ids = user.get("contacts", [])
    cursor = users_collection.find({"_id": {"$in": contact_ids}})
    contacts = await cursor.to_list(length=None)
    # Convert ObjectId fields to str for JSON serialization
    for c in contacts:
        c["_id"] = str(c.get("_id"))
        if "contacts" in c:
            c["contacts"] = [str(cid) for cid in c.get("contacts", [])]
    return contacts
