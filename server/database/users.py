# database/users.py
from bson import ObjectId
from pymongo import ReturnDocument
from database.db import get_collection

users_collection = get_collection("users")


def create_user(user_data):
    """
    Insert a new user document and return its unique ID.
    """
    result = users_collection.insert_one(user_data)
    return result.inserted_id


def get_user_by_id(user_id):
    """
    Retrieve a user document by its ObjectId.
    """
    if not isinstance(user_id, ObjectId):
        user_id = ObjectId(user_id)
    return users_collection.find_one({"_id": user_id})


def get_user_by_username(username):
    return users_collection.find_one({"username": username})


def add_contact_to_user(user_id, contact_username):
    """
    Add a contact's ObjectId to a user's contacts list.
    Uses $addToSet to avoid duplicate entries.
    """
    contact = get_user_by_username(contact_username)
    if not contact:
        return None
    contact_id = contact["_id"]
    result = users_collection.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$addToSet": {"contacts": ObjectId(contact_id)}},
        return_document=ReturnDocument.AFTER
    )
    return result


def get_user_contacts(user_id):
    """
    Retrieve full details for each contact in the user's contacts list.
    """
    user = get_user_by_id(user_id)
    if not user or "contacts" not in user:
        return []

    contact_ids = user["contacts"]
    # Query the users collection to fetch details of contacts.
    contacts = list(users_collection.find({"_id": {"$in": contact_ids}}))

    # Convert ObjectIds to strings for JSON serialization if needed.
    for contact in contacts:
        # Convert the contact's own _id to a string.
        contact["_id"] = str(contact["_id"])

        # If each contact document also has a 'contacts' field with ObjectIds,
        # convert those to strings as well.
        if "contacts" in contact:
            contact["contacts"] = [str(cid) for cid in contact["contacts"]]

    return contacts
