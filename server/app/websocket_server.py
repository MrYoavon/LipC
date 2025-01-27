import asyncio
import websockets
import json
import logging

connected_clients = {}  # Store connected clients by their unique ID (e.g., username/session ID)

async def handle_connection(websocket):
    """
    Handle a new WebSocket connection.
    """
    logging.info("New connection established.")
    try:
        # Receive and process messages
        async for message in websocket:
            await handle_message(websocket, message)
    except websockets.ConnectionClosed:
        logging.info("Connection closed.")
        await handle_disconnection(websocket)

async def handle_message(websocket, message):
    """
    Handle an incoming WebSocket message.
    """
    try:
        data = json.loads(message)  # Parse JSON message
        message_type = data.get("type")

        if message_type == "authenticate":
            await handle_authentication(websocket, data)
        elif message_type == "fetch_contacts":
            await fetch_contacts(websocket, data)
        elif message_type == "signaling":
            await handle_signaling(websocket, data)
        else:
            await websocket.send(json.dumps({"error": "Unknown message type"}))
    except json.JSONDecodeError:
        await websocket.send(json.dumps({"error": "Invalid JSON format"}))

async def handle_authentication(websocket, data):
    """
    Authenticate a client.
    """
    username = data.get("username")
    password = data.get("password")
    # Placeholder authentication logic
    if username and password:
        connected_clients[username] = websocket
        await websocket.send(json.dumps({"type": "authenticate", "success": True}))
        logging.info(f"User '{username}' authenticated.")
    else:
        await websocket.send(json.dumps({"type": "authenticate", "success": False}))

async def fetch_contacts(websocket, data):
    """
    Send a mock contact list to the client.
    """
    contacts = [{"id": "1", "name": "John"}, {"id": "2", "name": "Jane"}]
    await websocket.send(json.dumps({"type": "contacts", "data": contacts}))
    logging.info("Contacts sent.")

async def handle_signaling(websocket, data):
    """
    Relay WebRTC signaling data to the target client.
    """
    target = data.get("target")
    signaling_data = data.get("payload")

    if target in connected_clients:
        target_websocket = connected_clients[target]
        await target_websocket.send(json.dumps({"type": "signaling", "data": signaling_data}))
        logging.info(f"Signaling data relayed to {target}.")
    else:
        await websocket.send(json.dumps({"type": "error", "message": "Target client not connected."}))

async def handle_disconnection(websocket):
    """
    Remove a disconnected client.
    """
    for username, client in list(connected_clients.items()):
        if client == websocket:
            del connected_clients[username]
            logging.info(f"User '{username}' disconnected.")
            break

async def start_server():
    """
    Start the WebSocket server.
    """
    logging.basicConfig(level=logging.INFO)
    async with websockets.serve(handle_connection, "192.168.1.107", 8765):
        logging.info("WebSocket server started on ws://192.168.1.107:8765")
        await asyncio.Future()  # Keep the server running
