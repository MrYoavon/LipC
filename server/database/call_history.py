# database/call_history.py
"""
Database operations for call history management.

This module provides functions to start and finish calls,
append transcript lines, and retrieve call summaries or full transcripts.
"""
from datetime import datetime
from bson import ObjectId
from database.db import get_collection

# MongoDB collection for calls
calls = get_collection("calls")


def start_call(caller_id: str, callee_id: str) -> ObjectId:
    """
    Record the start of a new call between two users.

    Args:
        caller_id (str): ObjectId string of the calling user.
        callee_id (str): ObjectId string of the receiving user.

    Returns:
        ObjectId: The MongoDB _id of the newly created call document.

    Raises:
        PyMongoError: If insertion into the collection fails.
    """
    doc = {
        "caller_id": ObjectId(caller_id),
        "callee_id": ObjectId(callee_id),
        "started_at": datetime.now(),
        "ended_at": None,
        "duration_seconds": None,
        "transcripts": [],  # list of transcript entries
        # each item in transcripts: {"t": <datetime>, "speaker": ObjectId, "text": str, "source": "lip"|"vosk"}
    }
    result = calls.insert_one(doc)
    return result.inserted_id


def append_line(call_id: ObjectId, speaker_id: str, text: str, source: str = "lip") -> None:
    """
    Append a transcript entry to an ongoing call.

    Args:
        call_id (ObjectId): The _id of the call document.
        speaker_id (str): ObjectId string of the speaker user.
        text (str): Transcribed text for this entry.
        source (str): "lip" or "vosk", indicating transcription source.

    Returns:
        None

    Raises:
        PyMongoError: If update operation fails.
    """
    entry = {
        "t": datetime.now(),
        "speaker": ObjectId(speaker_id),
        "text": text,
        "source": source,
    }
    calls.update_one({"_id": ObjectId(call_id)}, {
                     "$push": {"transcripts": entry}})


def finish_call(call_id: ObjectId) -> None:
    """
    Mark a call as finished by setting end time and computing duration.

    Args:
        call_id (ObjectId): The _id of the call document.

    Returns:
        None

    Raises:
        PyMongoError: If update operation fails.
    """
    now = datetime.now()
    # Compute duration in seconds: (ended_at - started_at) / 1000 ms
    calls.update_one(
        {"_id": ObjectId(call_id)},
        [{"$set": {
            "ended_at": now,
            "duration_seconds": {
                "$divide": [{"$subtract": [now, "$started_at"]}, 1000]
            }
        }}]
    )


def get_call_history(user_id: str, limit: int = 50) -> list[dict]:
    """
    Retrieve recent calls involving a specific user, excluding transcripts.

    Args:
        user_id (str): ObjectId string of the user.
        limit (int): Maximum number of call records to return.

    Returns:
        list[dict]: List of call documents with stringified IDs and timestamps.

    Raises:
        PyMongoError: If query operation fails.
    """
    query = {"$or": [
        {"caller_id": ObjectId(user_id)},
        {"callee_id": ObjectId(user_id)}
    ]}
    cursor = calls.find(query).sort("started_at", -1).limit(limit)
    history = []
    for doc in cursor:
        # Convert ObjectId to str for JSON
        doc["_id"] = str(doc["_id"])
        doc["caller_id"] = str(doc["caller_id"])
        doc["callee_id"] = str(doc["callee_id"])
        history.append(doc)
    return history


def get_call_transcript(call_id: str) -> dict | None:
    """
    Retrieve the full call document including transcripts, formatted for transport.

    Args:
        call_id (str): ObjectId string of the call.

    Returns:
        dict | None: Call document with ISO-formatted timestamps and string IDs,
                      or None if not found.

    Raises:
        PyMongoError: If query operation fails.
    """
    doc = calls.find_one({"_id": ObjectId(call_id)})
    if doc is None:
        return None
    # Convert ObjectId fields to str
    doc["_id"] = str(doc["_id"])
    doc["caller_id"] = str(doc["caller_id"])
    doc["callee_id"] = str(doc["callee_id"])
    # Format transcript timestamps
    for line in doc.get("transcripts", []):
        line["t"] = line["t"].isoformat() + "Z"
        line["speaker"] = str(line["speaker"])
    return doc
