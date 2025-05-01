# handlers/call_history_handler.py
import logging

from database.call_history import get_call_history
from services.jwt_utils import verify_jwt_in_message
from services.crypto_utils import structure_encrypt_send_message, send_error_message


logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


async def _validate_jwt(ws, data, aes_key, msg_type):
    """
    Verify the JWT in the incoming message and extract context.

    Validates the provided JWT against expected token type 'access' and ensures
    it corresponds to the declared user_id. On failure, sends an encrypted
    error message back to the client.

    Args:
        ws: WebSocket connection for sending error responses.
        data (dict): Parsed message data containing 'jwt' and 'user_id'.
        aes_key (bytes): AES key for encryption of error message.
        msg_type (str): Identifier of the message type for context in errors.

    Returns:
        tuple: (user_id (str), payload (dict)) if valid; (None, None) if invalid.
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


def _serialize_entry(entry: dict) -> dict:
    """
    Convert a database call history entry to a JSON-serializable format.

    Transforms MongoDB ObjectId and datetime fields into strings, and formats
    transcript timestamps. Leaves text and speaker/source fields intact.

    Args:
        entry (dict): A single call history record from the database.

    Returns:
        dict: A JSON-serializable copy of the entry.
    """
    entry_copy = entry.copy()
    entry_copy["_id"] = str(entry_copy.get("_id"))
    entry_copy["caller_id"] = str(entry_copy.get("caller_id"))
    entry_copy["callee_id"] = str(entry_copy.get("callee_id"))
    entry_copy["started_at"] = entry_copy.get("started_at").isoformat() + "Z"
    entry_copy["ended_at"] = entry_copy.get("ended_at").isoformat() + "Z"

    transcripts = []
    for line in entry_copy.get("transcripts", []):
        transcripts.append({
            "t": line.get("t").isoformat() + "Z",
            "speaker": str(line.get("speaker")),
            "text": line.get("text"),
            "source": line.get("source"),
        })
    entry_copy["transcripts"] = transcripts
    return entry_copy

# -----------------------------------------------------------------------------
# Handler
# -----------------------------------------------------------------------------


async def handle_fetch_call_history(websocket, data, aes_key):
    """
    Retrieve and send the authenticated user's call history.

    Verifies the user's JWT, fetches up to `limit` entries (default 50) from the
    database, serializes each entry, and sends them encrypted back to the client.
    Handles and reports any errors during retrieval.

    Args:
        websocket: WebSocket connection for sending responses.
        data (dict): Parsed message data containing 'user_id', 'jwt', and optional 'payload.limit'.
        aes_key (bytes): AES key for encrypting the response or error.

    Returns:
        None
    """
    msg_type = "fetch_call_history"
    user_id, payload = await _validate_jwt(websocket, data, aes_key, msg_type)
    if user_id is None:
        return

    limit = payload.get("limit", 50)
    try:
        entries = get_call_history(user_id, limit)
        serialized = [_serialize_entry(e) for e in entries]

        logger.info(
            f"Fetched {len(serialized)} history entries for user {user_id}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            success=True,
            payload={"entries": serialized},
        )
    except Exception as exc:
        logger.error(f"Error fetching call history for user {user_id}: {exc}")
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="CALL_HISTORY_ERROR",
            error_message=str(exc),
        )
