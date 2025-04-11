# handlers/call_history.py
import json
from database.call_history import add_call_history, get_call_history
from services.crypto_utils import send_encrypted

async def handle_log_call(websocket, data, aes_key):
    """
    Handle a 'log_call' message by saving the call details.
    Expects data to contain: user_id, contact_id, contact_name, call_type, and duration_seconds.
    The response is encrypted using the provided AES key.
    """
    try:
        entry = {
            "user_id": data.get("user_id"),
            "contact_id": data.get("contact_id"),
            "contact_name": data.get("contact_name"),
            "call_type": data.get("call_type"),
            "duration_seconds": data.get("duration_seconds", 0)
        }
        inserted_id = add_call_history(entry)
        response = {
            "type": "log_call_response",
            "success": True,
            "call_history_id": str(inserted_id)
        }
    except Exception as e:
        response = {
            "type": "log_call_response",
            "success": False,
            "error": str(e)
        }
    await send_encrypted(websocket, json.dumps(response), aes_key)

async def handle_fetch_call_history(websocket, data, aes_key):
    """
    Handle a 'fetch_call_history' message by retrieving the user's call history.
    Expects data to contain the user_id and an optional limit.
    The response is encrypted using the provided AES key.
    """
    user_id = data.get("user_id")
    limit = data.get("limit", 50)
    try:
        entries = get_call_history(user_id, limit)
        # Convert any non-JSON-serializable fields.
        for entry in entries:
            entry["_id"] = str(entry["_id"])
            entry["timestamp"] = entry["timestamp"].isoformat() + "Z"
        response = {
            "type": "call_history",
            "entries": entries
        }
    except Exception as e:
        response = {
            "type": "call_history",
            "error": str(e)
        }
    await send_encrypted(websocket, json.dumps(response), aes_key)
