# handlers/contacts_handler.py
import logging

from database.users import add_contact_to_user, get_user_contacts
from services.jwt_utils import verify_jwt_in_message
from services.crypto_utils import structure_encrypt_send_message, send_error_message


logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


async def _validate_jwt(ws, data, aes_key, msg_type):
    """
    Verify JWT and return payload dict, or send an error and return None.
    """
    user_id = data.get("user_id")
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logger.warning(
            f"Invalid JWT for {msg_type}, user {user_id}: {result}")
        await send_error_message(
            websocket=ws,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code=result.get("error"),
            error_message=result.get("message"),
        )
        return None, None
    return user_id, data.get("payload", {})

# -----------------------------------------------------------------------------
# Contact Handlers
# -----------------------------------------------------------------------------


async def handle_add_contact(websocket, data, aes_key):
    """
    Add a new contact for the authenticated user.
    Expects 'contact_username' in payload.
    """
    user_id, payload = await _validate_jwt(websocket, data, aes_key, "add_contact")
    if payload is None:
        return

    contact_username = payload.get("contact_username")
    if not contact_username:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="add_contact",
            error_code="MISSING_FIELDS",
            error_message="contact_username is required.",
        )
        return

    updated = add_contact_to_user(user_id, contact_username)
    if not updated:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="add_contact",
            error_code="ADD_CONTACT_FAILED",
            error_message="Failed to add contact; user may not exist.",
        )
        return

    contacts = [str(cid) for cid in updated.get("contacts", [])]
    logger.info(f"Added contact '{contact_username}' for user '{user_id}'")
    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type="add_contact",
        success=True,
        payload={"contacts": contacts},
    )


async def handle_get_contacts(websocket, data, aes_key):
    """
    Retrieve all contacts for the authenticated user.
    """
    user_id, _ = await _validate_jwt(websocket, data, aes_key, "get_contacts")
    if user_id is None:
        return

    contacts = get_user_contacts(user_id)
    if contacts is None:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="get_contacts",
            error_code="FETCH_FAILED",
            error_message="Unable to retrieve contacts.",
        )
        return

    logger.info(f"Retrieved {len(contacts)} contacts for user '{user_id}'")
    contacts_data = [
        {
            "_id": str(contact.get("_id")),
            "username": contact.get("username"),
            "name": contact.get("name"),
            "profile_pic": contact.get("profile_pic"),
        }
        for contact in contacts
    ]

    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type="get_contacts",
        success=True,
        payload={"contacts": contacts_data},
    )
