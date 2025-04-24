from bson import ObjectId
from pymongo import ReturnDocument
from database.db import get_collection
import datetime

rt_collection = get_collection("refresh_tokens")


def save_refresh_token(user_id, jti, token_hash, expires_at):
    doc = {
        "user_id": ObjectId(user_id),
        "jti": jti,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "revoked": False,
        "created_at": datetime.datetime.now(),
        "replaced_by_jti": None
    }
    rt_collection.insert_one(doc)


def find_valid_token(jti, token_hash):
    return rt_collection.find_one({
        "jti": jti,
        "token_hash": token_hash,
        "revoked": False,
        "expires_at": {"$gt": datetime.datetime.now()}
    })


def revoke_token(jti):
    rt_collection.update_one(
        {"jti": jti},
        {"$set": {"revoked": True}}
    )


def revoke_previous_token(user_id: str, replaced_by_jti: str) -> str | None:
    """
    Find one non-revoked refresh token for this user, revoke it, and
    set its `replaced_by_jti` to the new token's JTI.

    Returns the old token's JTI if one was found and revoked, else None.
    """
    filter = {
        "user_id": ObjectId(user_id),
        "revoked": False
    }
    update = {
        "$set": {
            "revoked": True,
            "revoked_at": datetime.datetime.now(),
            "replaced_by_jti": replaced_by_jti
        }
    }

    # find_one_and_update returns the document *before* the update
    old = rt_collection.find_one_and_update(
        filter,
        update,
        # pick the most recent if there are multiple
        sort=[("created_at", -1)],
        return_document=ReturnDocument.BEFORE
    )
    if old:
        return old.get("jti")
    return None
