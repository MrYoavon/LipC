import os
import sys
import pytest
import asyncio

# ──────────────────────────────────────────────────────────────────────────────
# Make sure the `server/` dir (the parent of tests/) is on sys.path so that
# `import database.db` (and all your other imports) work.
# ──────────────────────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# Ensure tests use a separate MongoDB database
os.environ.setdefault("DATABASE_NAME", "lipc_test")

# fmt: off
from database.db import client
# fmt: on


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    db_name = os.environ["DATABASE_NAME"]
    db = client[db_name]
    # drop any existing collections
    for coll in db.list_collection_names():
        db.drop_collection(coll)

    yield

    # clean up again at teardown
    for coll in db.list_collection_names():
        db.drop_collection(coll)


@pytest.fixture(scope="session")
def event_loop():
    """Provide a shared event loop for pytest-asyncio."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
