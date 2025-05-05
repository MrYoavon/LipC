"""
Database operations for refresh token lifecycle management.

This module provides functions to save, validate, and revoke refresh tokens,
as well as to replace previous tokens for a user.
"""
from bson import ObjectId
from pymongo import ReturnDocument
from database.db import get_collection
import datetime

# MongoDB collection for refresh token documents
rt_collection = get_collection("refresh_tokens")


async def save_refresh_token(user_id: str, jti: str, token_hash: str, expires_at: datetime.datetime) -> None:
    """
    Persist a new refresh token record in the database.

    Args:
        user_id (str): String form of the user's ObjectId.
        jti (str): Unique identifier (JWT ID) for the refresh token.
        token_hash (str): SHA-256 hash of the refresh token.
        expires_at (datetime.datetime): UTC timestamp when the token expires.

    Returns:
        None
    """
    doc = {
        "user_id": ObjectId(user_id),
        "jti": jti,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "revoked": False,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "replaced_by_jti": None,
        "revoked_at": None
    }
    await rt_collection.insert_one(doc)


async def find_valid_token(jti: str, token_hash: str) -> dict | None:
    """
    Retrieve a non-revoked, unexpired refresh token by its JTI and hash.

    Args:
        jti (str): JWT ID of the token to find.
        token_hash (str): SHA-256 hash of the token to find.

    Returns:
        dict | None: The token document if valid, otherwise None.

    Raises:
        PyMongoError: If the query fails.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    return await rt_collection.find_one({
        "jti": jti,
        "token_hash": token_hash,
        "revoked": False,
        "expires_at": {"$gt": now}
    })


async def revoke_token(jti: str) -> None:
    """
    Mark a specific refresh token as revoked.

    Args:
        jti (str): JWT ID of the token to revoke.

    Returns:
        None

    Raises:
        PyMongoError: If the update operation fails.
    """
    await rt_collection.update_one(
        {"jti": jti},
        {"$set": {"revoked": True, "revoked_at": datetime.datetime.now(
            datetime.timezone.utc)}}
    )


async def revoke_previous_token(user_id: str, replaced_by_jti: str) -> str | None:
    """
    Revoke the most recently created, non-revoked refresh token for a user.

    Finds one existing token for the given user that is not yet revoked,
    sets its revoked flag and `replaced_by_jti` field to the new JTI.

    Args:
        user_id (str): String form of the user's ObjectId.
        replaced_by_jti (str): JTI of the new token that replaces the old one.

    Returns:
        str | None: The JTI of the revoked token if one was found; otherwise None.

    Raises:
        PyMongoError: If the find-and-update operation fails.
    """
    filter_query = {"user_id": ObjectId(user_id), "revoked": False}
    update = {
        "$set": {
            "revoked": True,
            "revoked_at": datetime.datetime.now(datetime.timezone.utc),
            "replaced_by_jti": replaced_by_jti
        }
    }
    # Find the most recent valid token and revoke it
    old = await rt_collection.find_one_and_update(
        filter_query,
        update,
        sort=[("created_at", -1)],
        return_document=ReturnDocument.BEFORE
    )
    return old.get("jti") if old else None
