# handlers/contacts_handler.py
import logging

from database.users import add_contact_to_user, get_user_contacts
from services.jwt_utils import verify_jwt_in_message
from services.crypto_utils import structure_encrypt_send_message, send_error_message


logger = logging.getLogger(__name__)


class ContactsHandler:
    """
    Handles adding and fetching user contacts.
    """

    async def handle_add_contact(self, websocket, data, aes_key):
        """
        Add a new contact for the authenticated user.

        Validates the requester's JWT, extracts the 'contact_username' from payload,
        and updates the user's contact list in the database. Returns the updated list.

        Args:
            websocket: WebSocket connection for communication.
            data (dict): Parsed message data containing 'user_id', 'jwt', and payload.
            aes_key (bytes): AES key for encrypting responses.

        Returns:
            None

        Side Effects:
            Sends an encrypted success or error message over the WebSocket.
        """
        user_id, payload = await self._validate_jwt(websocket, data, aes_key, "add_contact")
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

        updated = await add_contact_to_user(user_id, contact_username)
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

    async def handle_get_contacts(self, websocket, data, aes_key):
        """
        Retrieve all contacts for the authenticated user.

        Validates the requester's JWT and fetches the user's contacts from the database.
        Serializes each contact to a JSON-friendly format and returns the list.

        Args:
            websocket: WebSocket connection for communication.
            data (dict): Parsed message data containing 'user_id' and 'jwt'.
            aes_key (bytes): AES key for encrypting responses.

        Returns:
            None

        Side Effects:
            Sends an encrypted success or error message over the WebSocket.
        """
        user_id, _ = await self._validate_jwt(websocket, data, aes_key, "get_contacts")
        if user_id is None:
            return

        contacts = await get_user_contacts(user_id)
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

    async def _validate_jwt(self, ws, data, aes_key, msg_type):
        """
        Verify the JWT in an incoming message and extract the payload.

        Checks the provided JWT against expected token type 'access' and ensures
        it corresponds to the declared user_id. On failure, sends an encrypted
        error over the WebSocket.

        Args:
            ws: WebSocket connection for sending error responses.
            data (dict): Parsed message data containing 'jwt' and 'user_id'.
            aes_key (bytes): AES key for encrypting the error message.
            msg_type (str): The type of the message being handled, used for logging.

        Returns:
            tuple:
                - user_id (str) if valid, else None
                - payload (dict) if valid, else None
        """
        user_id = data.get("user_id")
        valid, result = verify_jwt_in_message(
            data.get("jwt"), "access", user_id)
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
