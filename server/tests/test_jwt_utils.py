from bson import ObjectId
import pytest
import os
from services.jwt_utils import (
    create_access_token, create_refresh_token,
    verify_jwt, verify_jwt_in_message, refresh_access_token
)


def test_jwt_roundtrip(tmp_path, monkeypatch):
    # Use env RSA keys (assumed set in your shell already)
    uid = str(ObjectId())

    # Access token
    at = create_access_token(uid)
    payload = verify_jwt(at, expected_type="access")
    assert payload["sub"] == uid and payload["type"] == "access"

    # Refresh token
    rt = create_refresh_token(uid)
    ok, data = verify_jwt_in_message(rt, "refresh", uid)
    assert ok and data["sub"] == uid

    # New access via refresh
    new_at = refresh_access_token(rt)
    p2 = verify_jwt(new_at, expected_type="access")
    assert p2["sub"] == uid
