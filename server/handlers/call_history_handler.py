# handlers/call_history.py
import logging
from database.call_history import get_call_history
from services.jwt_utils import verify_jwt_in_message
from services.crypto_utils import structure_encrypt_send_message


async def handle_fetch_call_history(websocket, data, aes_key):
    """
    Handle a 'fetch_call_history' message by retrieving the user's call history.
    Expects data to contain the user_id and an optional limit.
    Performs JWT verification and responds with a structured message containing the call history,
    or error details if an exception occurs.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    limit = payload.get("limit", 50)

    # Verify the JWT token.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="fetch_call_history",
            success=False,
            error_code=result["error"],
            error_message=result["message"]
        )
        return

    try:
        entries = get_call_history(user_id, limit)
        # Convert any non-JSON-serializable fields.
        for entry in entries:
            entry["_id"] = str(entry["_id"])
            entry["started_at"] = entry["started_at"].isoformat() + "Z"
            entry["ended_at"] = entry["ended_at"].isoformat() + "Z"
            entry["caller_id"] = str(entry["caller_id"])
            entry["callee_id"] = str(entry["callee_id"])
            for line in entry.get("transcripts", []):
                line["t"] = line["t"].isoformat() + "Z"
                line["speaker"] = str(line["speaker"])
        response_data = {
            "entries": entries
        }
        logging.info(
            f"Fetched call history for user {user_id}: {response_data}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="fetch_call_history",
            success=True,
            payload=response_data
        )
    except Exception as e:
        logging.error(f"Error fetching call history for user {user_id}: {e}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="fetch_call_history",
            success=False,
            error_code="CALL_HISTORY_ERROR",
            error_message=str(e)
        )
