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
    Verify JWT and return user_id and payload; send error if verification fails.
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
    Convert Mongo-specific and datetime fields to JSON-serializable formats.
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
    Retrieve and return the authenticated user's call history.
    Supports optional 'limit' in payload (default=50).
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
