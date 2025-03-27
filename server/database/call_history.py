# database/call_history.py
from datetime import datetime
from database.db import get_collection

call_history_collection = get_collection("call_history")

def add_call_history(entry):
    """
    Insert a call history entry into the database.
    Expected entry keys:
      - user_id: The ID of the user making or receiving the call.
      - contact_id: The contact's ID.
      - contact_name: Name of the contact.
      - call_type: 'incoming', 'outgoing', or 'missed'.
      - duration_seconds: Call duration (defaults to 0 if not provided).
    If no timestamp is provided, the current time is used.
    """
    if "timestamp" not in entry:
        entry["timestamp"] = datetime.now()
    result = call_history_collection.insert_one(entry)
    return result.inserted_id

def get_call_history(user_id, limit=50):
    """
    Retrieve call history for a given user, sorted by the most recent call.
    """
    cursor = call_history_collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    entries = list(cursor)
    return entries
