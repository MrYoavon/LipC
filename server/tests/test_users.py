import pytest
from bson import ObjectId
from database.users import (
    create_user, get_user_by_username, get_user_by_id,
    add_contact_to_user, get_user_contacts
)


def test_user_crud_and_contacts():
    # Create two users
    uid1 = create_user({
        "username": "alice", "password_hash": "hash", "name": "Alice A", "contacts": []
    })
    uid2 = create_user({
        "username": "bob", "password_hash": "hash2", "name": "Bob B", "contacts": []
    })

    # Retrieval by username & by id
    u1 = get_user_by_username("alice")
    assert u1 and str(u1["_id"]) == str(uid1)
    u2 = get_user_by_id(uid2)
    assert u2 and u2["username"] == "bob"

    # Add Bob as Alice’s contact
    updated = add_contact_to_user(uid1, "bob")
    assert updated and ObjectId(uid2) in updated["contacts"]

    # Fetch contacts list
    contacts = get_user_contacts(uid1)
    assert len(contacts) == 1
    assert contacts[0]["username"] == "bob"
