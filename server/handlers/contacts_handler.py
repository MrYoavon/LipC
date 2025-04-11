# handlers/contacts.py
import json
import logging
from database.users import add_contact_to_user, get_user_contacts
from services.crypto_utils import send_encrypted

async def handle_add_contact(websocket, data, aes_key):
    """
    Handle a request to add a contact for the authenticated user.
    Expects data to contain:
      - user_id: the ID of the current user
      - contact_username: the username of the user to add as a contact
    The response is encrypted using the provided AES key.
    """
    user_id = data.get("user_id")
    contact_username = data.get("contact_username")
    
    if not user_id or not contact_username:
        response = {
            "type": "add_contact",
            "success": False,
            "reason": "user_id and contact_username are required."
        }
        await send_encrypted(websocket, json.dumps(response), aes_key)
        return

    updated_user = add_contact_to_user(user_id, contact_username)
    if updated_user:
        logging.info(f"Added contact {contact_username} for user {user_id}")
        response = {
            "type": "add_contact",
            "success": True,
            "contacts": [str(cid) for cid in updated_user.get("contacts", [])]
        }
    else:
        response = {
            "type": "add_contact",
            "success": False,
            "reason": "Failed to add contact. Most likely the user does not exist."
        }
    await send_encrypted(websocket, json.dumps(response), aes_key)

async def handle_get_contacts(websocket, data, aes_key):
    """
    Handle a request to retrieve all contacts for a user.
    Expects data to contain:
      - user_id: the ID of the current user
    The response is encrypted using the provided AES key.
    """
    user_id = data.get("user_id")
    
    if not user_id:
        response = {
            "type": "get_contacts",
            "success": False,
            "reason": "user_id is required."
        }
        await send_encrypted(websocket, json.dumps(response), aes_key)
        return
    
    contacts = get_user_contacts(user_id)
    logging.info(f"Retrieved {len(contacts)} contacts for user {user_id}")

    # Remove private information from contacts.
    contacts = [{
        "_id": str(contact.get("_id")),
        "username": contact.get("username"),
        "name": contact.get("name"),
        "profile_pic": contact.get("profile_pic")
    } for contact in contacts]
    
    response = {
        "type": "get_contacts",
        "success": True,
        "contacts": contacts
    }
    await send_encrypted(websocket, json.dumps(response), aes_key)
