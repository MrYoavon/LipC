# database/call_history.py
from datetime import datetime
from bson import ObjectId
from database.db import get_collection

calls = get_collection("calls")


def start_call(caller_id: str, callee_id: str) -> ObjectId:
    """
    Create a new call document and return its _id.
    """
    doc = {
        "caller_id": ObjectId(caller_id),
        "callee_id": ObjectId(callee_id),
        "started_at": datetime.now(),
        "ended_at": None,
        "duration_seconds": None,
        # each item: {"t": <datetime>, "speaker": ObjectId, "text": str, "source": "lip"|"vosk"}
        "transcripts": [],
        # room for future stats (frame counts, WER, …)
        "meta": {}
    }
    return calls.insert_one(doc).inserted_id


def append_line(call_id: ObjectId, speaker_id: str, text: str,
                source: str = "lip") -> None:
    calls.update_one(
        {"_id": ObjectId(call_id)},
        {"$push": {"transcripts": {
            "t": datetime.now(),
            "speaker": ObjectId(speaker_id),
            "text": text,
            "source": source
        }}}
    )


def finish_call(call_id: ObjectId) -> None:
    """
    Mark call finished and store the duration.
    """
    now = datetime.now()
    calls.update_one(
        {"_id": ObjectId(call_id)},
        [{"$set": {
            "ended_at": now,
            "duration_seconds": {
                "$divide": [{"$subtract": [now, "$started_at"]}, 1000]
            }}
          }]
    )


def get_call_history(user_id: str, limit: int = 50):
    """
    Return the most recent calls *involving* this user (no transcript payload).
    """
    cursor = (calls
              .find({"$or": [
                  {"caller_id": ObjectId(user_id)},
                  {"callee_id": ObjectId(user_id)}
              ]},
              )
              .sort("started_at", -1)
              .limit(limit))
    # stringify ObjectIds for JSON serialisation
    out = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["caller_id"] = str(doc["caller_id"])
        doc["callee_id"] = str(doc["callee_id"])
        out.append(doc)
    return out


def get_call_transcript(call_id: str):
    """
    Full record including transcript ready to render as a chat.
    """
    doc = calls.find_one({"_id": ObjectId(call_id)})
    if not doc:
        return None
    # string‑ify for transport
    doc["_id"] = str(doc["_id"])
    doc["caller_id"] = str(doc["caller_id"])
    doc["callee_id"] = str(doc["callee_id"])
    for line in doc["transcripts"]:
        line["t"] = line["t"].isoformat() + "Z"
        line["speaker"] = str(line["speaker"])
    return doc
