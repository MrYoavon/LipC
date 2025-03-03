# utils/contacts.py
import json
import logging

async def fetch_contacts(websocket, data):
    """
    Send a mock contact list to the client.
    """
    contacts = [{"id": "1", "name": "John"}, {"id": "2", "name": "Jane"}]
    await websocket.send(json.dumps({"type": "contacts", "data": contacts}))
    logging.info("Contacts sent.")
