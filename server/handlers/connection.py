# server/handlers/connection.py
import asyncio
import json
import logging
import time
import traceback

from services.state import clients
from handlers.auth_handler import handle_authentication, handle_signup
from handlers.contacts_handler import handle_get_contacts, handle_add_contact
from handlers.call_handler import (
    handle_call_invite, handle_call_accept, handle_call_reject,
    handle_call_end, handle_video_state
)
from handlers.signaling_handler import handle_offer, handle_answer, handle_ice_candidate
from handlers.call_history_handler import handle_log_call, handle_fetch_call_history


async def handle_connection(websocket):
    """
    Handle a new WebSocket connection with heartbeat monitoring.
    """
    logging.info("New connection established.")
    last_ping = time.time()

    async def heartbeat_check():
        """Periodically check if a ping has been received recently."""
        while True:
            await asyncio.sleep(10)
            if time.time() - last_ping > 15:
                logging.warning("No ping received from client in threshold; closing connection.")
                await websocket.close()
                break

    # Start the heartbeat checker as a background task.
    heartbeat_task = asyncio.create_task(heartbeat_check())

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "ping":
                    # Update the last ping timestamp.
                    last_ping = time.time()
                    # Respond with a pong.
                    await websocket.send(json.dumps({"type": "pong"}))
                else:
                    # Dispatch other message types as usual.
                    await dispatch_message(websocket, message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON format"}))
    except Exception as e:
        logging.error(f"Connection error: {e}\n{traceback.format_exc()}")
    finally:
        heartbeat_task.cancel()  # Cancel the heartbeat check when done.
        await handle_disconnection(websocket)


async def dispatch_message(websocket, message):
    """
    Parse and route an incoming message to the correct handler.
    """
    try:
        data = json.loads(message)
        message_type = data.get("type")

        if message_type == "authenticate":
            await handle_authentication(websocket, data)
        elif message_type == "signup":
            await handle_signup(websocket, data)
        elif message_type == "get_contacts":
            await handle_get_contacts(websocket, data)
        elif message_type == "add_contact":
            await handle_add_contact(websocket, data)
        elif message_type == "call_invite":
            await handle_call_invite(websocket, data)
        elif message_type == "call_accept":
            await handle_call_accept(websocket, data)
        elif message_type == "call_reject":
            await handle_call_reject(websocket, data)
        elif message_type == "call_end":
            await handle_call_end(websocket, data)
        elif message_type == "video_state":
            await handle_video_state(websocket, data)
        elif message_type == "offer":
            await handle_offer(websocket, data)
        elif message_type == "answer":
            await handle_answer(websocket, data)
        elif message_type == "ice_candidate":
            await handle_ice_candidate(websocket, data)
        elif message_type == "log_call":
            await handle_log_call(websocket, data)
        elif message_type == "fetch_call_history":
            await handle_fetch_call_history(websocket, data)
        else:
            logging.warning(f"Unknown message type: {message_type}")
            await websocket.send(json.dumps({"error": "Unknown message type"}))
    except json.JSONDecodeError:
        await websocket.send(json.dumps({"error": "Invalid JSON format"}))


async def handle_disconnection(websocket):
    """
    Cleanup when a client disconnects.
    """
    disconnected_username = None
    for username, info in list(clients.items()):
        if info["ws"] == websocket:
            # Close PeerConnection if any
            if info["pc"]:
                await info["pc"].close()
            disconnected_username = username
            break
    if disconnected_username:
        logging.info(f"User {disconnected_username} disconnected.")
        del clients[disconnected_username]
