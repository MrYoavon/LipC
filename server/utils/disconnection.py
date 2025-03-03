# utils/disconnection.py
import json
import logging
from .state import clients

async def handle_disconnection(websocket):
    """
    Remove a disconnected client.
    """
    disconnected_username = None
    for username, info in list(clients.items()):
        if info["ws"] == websocket:
            if info["pc"]:
                await info["pc"].close()
            disconnected_username = username
            break
    if disconnected_username:
        logging.info(f"User {disconnected_username} disconnected.")
        del clients[disconnected_username]
