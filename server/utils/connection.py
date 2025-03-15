# utils/connection.py
import json
import logging
from .auth import handle_authentication
from .contacts import fetch_contacts
from .call_control import handle_call_invite, handle_call_accept, handle_call_reject
from .signaling import handle_offer, handle_answer, handle_ice_candidate
from .disconnection import handle_disconnection

async def handle_message(websocket, message):
    """
    Handle an incoming WebSocket message.
    """
    try:
        data = json.loads(message)
        message_type = data.get("type")

        if message_type == "authenticate":
            await handle_authentication(websocket, data)
        elif message_type == "fetch_contacts":
            await fetch_contacts(websocket, data)
        elif message_type == "call_invite":
            await handle_call_invite(websocket, data)
        elif message_type == "call_accept":
            await handle_call_accept(websocket, data)
        elif message_type == "call_reject":
            await handle_call_reject(websocket, data)
        elif message_type == "offer":
            await handle_offer(websocket, data)
        elif message_type == "answer":
            await handle_answer(websocket, data)
        elif message_type == "ice_candidate":
            await handle_ice_candidate(websocket, data)
        else:
            await websocket.send(json.dumps({"error": "Unknown message type"}))
    except json.JSONDecodeError:
        await websocket.send(json.dumps({"error": "Invalid JSON format"}))

async def handle_connection(websocket):
    """
    Handle a new WebSocket connection.
    """
    logging.info("New connection established.")
    # try:
    async for message in websocket:
        await handle_message(websocket, message)
    # except Exception as e:
    #     logging.error(f"Connection error: {e}")
    # finally:
    #     await handle_disconnection(websocket)
