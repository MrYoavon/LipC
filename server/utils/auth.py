# utils/auth.py
import json
import logging
from .state import clients

async def handle_authentication(websocket, data):
    """
    Authenticate a client.
    """
    username = data.get("username")
    password = data.get("password")
    # Placeholder authentication logic.
    if username and password:
        clients[username] = {"ws": websocket, "pc": None}
        await websocket.send(json.dumps({"type": "authenticate", "success": True}))
        logging.info(f"User '{username}' authenticated.")
    else:
        await websocket.send(json.dumps({"type": "authenticate", "success": False}))
