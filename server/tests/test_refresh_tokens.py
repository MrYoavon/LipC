import pytest
import datetime
from database.refresh_tokens import (
    save_refresh_token, find_valid_token,
    revoke_token, revoke_previous_token
)


@pytest.mark.asyncio
async def test_refresh_token_lifecycle():
    user_id = "507f1f77bcf86cd799439011"
    jti1, jti2 = "jti-one", "jti-two"
    hash1, hash2 = "h1", "h2"
    expires = datetime.datetime.now(
        datetime.timezone.utc) + datetime.timedelta(hours=1)

    await save_refresh_token(user_id, jti1, hash1, expires)
    assert await find_valid_token(jti1, hash1)["jti"] == jti1

    # Revoke it via revoke_previous_token
    prev = await revoke_previous_token(user_id, jti2)
    assert prev == jti1
    assert await find_valid_token(jti1, hash1) is None

    # Now save a new one and revoke by id
    await save_refresh_token(user_id, jti2, hash2, expires)
    await revoke_token(jti2)
    assert await find_valid_token(jti2, hash2) is None
