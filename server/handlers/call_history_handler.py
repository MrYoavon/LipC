# handlers/call_history.py
import json
import logging
from database.call_history import add_call_history, get_call_history
from services.jwt_utils import verify_jwt_in_message
from services.crypto_utils import structure_encrypt_send_message

async def handle_log_call(websocket, data, aes_key):
    """
    Handle a 'log_call' message by saving the call details.
    Expects data to contain: user_id, contact_id, contact_name, call_type, and duration_seconds.
    Responds with a structured message that includes a unique call_history_id if successful,
    or proper error details if an exception occurs.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    contact_id = payload.get("contact_id")
    contact_name = payload.get("contact_name")
    call_type = payload.get("call_type")
    duration_seconds = payload.get("duration_seconds", 0)

    # Verify the JWT token.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="log_call_response",
            success=False,
            error_code=result["error"],
            error_message=result["message"]
        )
        return

    try:
        entry = {
            "user_id": user_id,
            "contact_id": contact_id,
            "contact_name": contact_name,
            "call_type": call_type,
            "duration_seconds": duration_seconds
        }
        inserted_id = add_call_history(entry)
        response_data = {
            "call_history_id": str(inserted_id)
        }
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="log_call_response",
            success=True,
            payload=response_data
        )
    except Exception as e:
        logging.error(f"Error logging call for user {user_id}: {e}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="log_call_response",
            success=False,
            error_code="CALL_HISTORY_ERROR",
            error_message=str(e)
        )

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
            entry["timestamp"] = entry["timestamp"].isoformat() + "Z"
        response_data = {
            "entries": entries
        }
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
