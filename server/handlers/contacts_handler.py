# handlers/contacts.py
import logging
from database.users import add_contact_to_user, get_user_contacts
from services.crypto_utils import structure_encrypt_send_message
from services.jwt_utils import verify_jwt_in_message

async def handle_add_contact(websocket, data, aes_key):
    """
    Handle a request to add a contact for the authenticated user.
    Expects data to contain:
      - user_id: the ID of the current user
      - contact_username: the username of the user to add as a contact
    The response is structured, encrypted, and sent using the provided AES key.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    contact_username = payload.get("contact_username")
    
    if not user_id or not contact_username:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="add_contact",
            success=False,
            error_code="MISSING_FIELDS",
            error_message="user_id and contact_username are required."
        )
        return
    
    # Verify the JWT token.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="add_contact",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    updated_user = add_contact_to_user(user_id, contact_username)
    if updated_user:
        logging.info(f"Added contact {contact_username} for user {user_id}")
        contacts_list = [str(cid) for cid in updated_user.get("contacts", [])]
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="add_contact",
            success=True,
            payload={"contacts": contacts_list}
        )
    else:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="add_contact",
            success=False,
            error_code="ADD_CONTACT_FAILED",
            error_message="Failed to add contact. Most likely the user does not exist."
        )


async def handle_get_contacts(websocket, data, aes_key):
    """
    Handle a request to retrieve all contacts for a user.
    Expects data to contain:
      - user_id: the ID of the current user
    The response is structured, encrypted, and sent using the provided AES key.
    """
    user_id = data.get("user_id")
    
    if not user_id:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="get_contacts",
            success=False,
            error_code="MISSING_USER_ID",
            error_message="user_id is required."
        )
        return

    # Verify the JWT token.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="get_contacts",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    contacts = get_user_contacts(user_id)
    logging.info(f"Retrieved {len(contacts)} contacts for user {user_id}")

    # Output only the wanted fields
    contacts_data = [{
        "_id": str(contact.get("_id")),
        "username": contact.get("username"),
        "name": contact.get("name"),
        "profile_pic": contact.get("profile_pic")
    } for contact in contacts]
    
    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type="get_contacts",
        success=True,
        payload={"contacts": contacts_data}
    )