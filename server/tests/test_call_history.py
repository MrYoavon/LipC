import pytest
from bson import ObjectId
from database.call_history import (
    start_call, append_line, finish_call,
    get_call_history, get_call_transcript
)


@pytest.mark.asyncio
async def test_call_history_lifecycle():
    # Start a call
    caller, callee = ObjectId(), ObjectId()
    call_id = await start_call(str(caller), str(callee))
    assert isinstance(call_id, ObjectId)

    # Append two lines
    await append_line(call_id, str(caller), "hello", source="lip")
    await append_line(call_id, str(callee), "hi", source="vosk")

    # Finish it
    await finish_call(call_id)

    # History list should include this call
    hist = await get_call_history(str(caller), limit=10)
    assert any(h["_id"] == str(call_id) for h in hist)

    # Full transcript view
    doc = await get_call_transcript(str(call_id))
    assert doc and "transcripts" in doc and len(doc["transcripts"]) == 2
