# database/contacts.py
from database.db import get_collection
from bson import ObjectId

contacts_collection = get_collection("contacts")

def add_contact(user_id, contact_data):
    """
    Add a contact to a user's contact list.
    """
    contact_data["user_id"] = ObjectId(user_id)
    result = contacts_collection.insert_one(contact_data)
    return result.inserted_id

def get_contacts(user_id):
    """
    Retrieve contacts for a given user.
    """
    return list(contacts_collection.find({"user_id": ObjectId(user_id)}))
