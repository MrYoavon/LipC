# # utils/contacts.py
# import json
# import logging

# async def fetch_contacts(websocket, data):
#     """
#     Send a mock contact list to the client.
#     """
#     contacts = [{"id": "1", "name": "John"}, {"id": "2", "name": "Jane"}]
#     await websocket.send(json.dumps({"type": "contacts", "data": contacts}))
#     logging.info("Contacts sent.")


# utils/contacts.py
import json
import logging
from database.users import add_contact_to_user, get_user_contacts

async def handle_add_contact(websocket, data):
    """
    Handle a request to add a contact for the authenticated user.
    Expect data to contain:
      - user_id: the ID of the current user
      - contact_username: the username of the user to add as a contact
    """
    user_id = data.get("user_id")
    contact_username = data.get("contact_username")
    
    if not user_id or not contact_username:
        await websocket.send(json.dumps({
            "type": "add_contact",
            "success": False,
            "reason": "user_id and contact_username are required."
        }))
        return

    updated_user = add_contact_to_user(user_id, contact_username)
    if updated_user:
        logging.info(f"Added contact {contact_username} for user {user_id}")
        await websocket.send(json.dumps({
            "type": "add_contact",
            "success": True,
            "contacts": [str(cid) for cid in updated_user.get("contacts", [])]
        }))
    else:
        await websocket.send(json.dumps({
            "type": "add_contact",
            "success": False,
            "reason": "Failed to add contact. Most likely the user does not exist."
        }))

async def handle_get_contacts(websocket, data):
    """
    Handle a request to retrieve all contacts for a user.
    Expect data to contain:
      - user_id: the ID of the current user
    """
    user_id = data.get("user_id")
    
    if not user_id:
        await websocket.send(json.dumps({
            "type": "get_contacts",
            "success": False,
            "reason": "user_id is required."
        }))
        return
    
    contacts = get_user_contacts(user_id)
    logging.info(f"Retrieved {len(contacts)} contacts for user {user_id}")

    # Remove private information from the contacts like password
    contacts = [{"_id": str(contact.get("_id")), "username": contact.get("username"), "name": contact.get("name"), "profile_pic": contact.get("profile_pic")} for contact in contacts]
    
    await websocket.send(json.dumps({
        "type": "get_contacts",
        "success": True,
        "contacts": contacts
    }))
