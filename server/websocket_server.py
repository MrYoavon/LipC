# import asyncio
# import websockets
# import json
# import logging

# # A dictionary mapping client IDs to their peer connections and WebSocket objects.
# clients = {}  # e.g., { "clientA": {"pc": RTCPeerConnection, "ws": websocket}, ... }

# async def handle_connection(websocket):
#     """
#     Handle a new WebSocket connection.
#     """
#     logging.info("New connection established.")
#     try:
#         # Receive and process messages
#         async for message in websocket:
#             await handle_message(websocket, message)
#     except websockets.ConnectionClosed:
#         logging.info("Connection closed.")
#         await handle_disconnection(websocket)

# async def handle_message(websocket, message):
#     """
#     Handle an incoming WebSocket message.
#     """
#     try:
#         data = json.loads(message)  # Parse JSON message
#         message_type = data.get("type")

#         if message_type == "authenticate":
#             await handle_authentication(websocket, data)
#         elif message_type == "fetch_contacts":
#             await fetch_contacts(websocket, data)
#         elif message_type == "offer":
#                 await handle_offer(websocket, data)
#         elif message_type == "answer":
#             await handle_answer(websocket, data)
#         elif message_type == "ice_candidate":
#             await handle_ice_candidate(websocket, data)
#         else:
#             await websocket.send(json.dumps({"error": "Unknown message type"}))
#     except json.JSONDecodeError:
#         await websocket.send(json.dumps({"error": "Invalid JSON format"}))

# async def handle_authentication(websocket, data):
#     """
#     Authenticate a client.
#     """
#     username = data.get("username")
#     password = data.get("password")
#     # Placeholder authentication logic
#     if username and password:
#         clients[username] = {"ws": websocket, "pc": None}
#         await websocket.send(json.dumps({"type": "authenticate", "success": True}))
#         logging.info(f"User '{username}' authenticated.")
#     else:
#         await websocket.send(json.dumps({"type": "authenticate", "success": False}))

# async def fetch_contacts(websocket, data):
#     """
#     Send a mock contact list to the client.
#     """
#     contacts = [{"id": "1", "name": "John"}, {"id": "2", "name": "Jane"}]
#     await websocket.send(json.dumps({"type": "contacts", "data": contacts}))
#     logging.info("Contacts sent.")

# async def handle_offer(websocket, data):
#     # data should contain: from, target, and offer (SDP)
#     sender = data.get("from")
#     target = data.get("target")
#     offer = data.get("offer")
#     logging.info(f"Received offer from {sender} to {target}")
#     if sender not in clients:
#         await websocket.send(json.dumps({"type": "error", "message": "Sender not authenticated."}))
#         return

#     # Create a new RTCPeerConnection for the sender if it doesn't exist.
#     pc = RTCPeerConnection()
#     clients[sender]["pc"] = pc

#     @pc.on("track")
#     def on_track(track):
#         logging.info(f"Track received from {sender}: {track.kind}")
#         if track.kind == "video":
#             # Subscribe to the incoming video track.
#             forwarded_track = relay.subscribe(track)
#             # If the target is connected, add the track to its peer connection.
#             if target in clients and clients[target]["pc"]:
#                 clients[target]["pc"].addTrack(forwarded_track)
#             # Here you can also feed the track into your lip reading model.
#             # For example:
#             # subtitles = run_lip_reading(forwarded_track)
#             # Then, send subtitles to both clients via websocket.

#     # Set remote description using the received offer.
#     await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
#     answer = await pc.createAnswer()
#     await pc.setLocalDescription(answer)

#     # Relay the answer back to the sender (or through the signaling channel to the target, depending on your flow)
#     response = {
#         "type": "answer",
#         "from": sender,
#         "to": target,
#         "answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
#     }
#     await websocket.send(json.dumps(response))
#     logging.info(f"Sent answer from server to {sender}")

# async def handle_answer(websocket, data):
#     # When the target sends an answer back.
#     sender = data.get("from")
#     target = data.get("target")
#     answer = data.get("answer")
#     logging.info(f"Received answer from {sender} for {target}")
#     if target in clients and clients[target]["pc"]:
#         pc = clients[target]["pc"]
#         await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
#         logging.info(f"Set remote description for {target}")
#     else:
#         await websocket.send(json.dumps({"type": "error", "message": "Target peer connection not found."}))

# async def handle_ice_candidate(websocket, data):
#     candidate = data.get("candidate")
#     sender = data.get("from")
#     target = data.get("target")
#     logging.info(f"ICE candidate from {sender} for {target}")
#     if sender in clients and clients[sender]["pc"]:
#         pc = clients[sender]["pc"]
#         # Add the candidate to the peer connection.
#         await pc.addIceCandidate(candidate)
#     else:
#         await websocket.send(json.dumps({"type": "error", "message": "Peer connection not found."}))

# async def handle_disconnection(websocket):
#     # Remove disconnected clients.
#     for username, info in list(clients.items()):
#         if info["ws"] == websocket:
#             if info["pc"]:
#                 await info["pc"].close()
#             del clients[username]
#             logging.info(f"User '{username}' disconnected.")
#             break

# async def start_server():
#     """
#     Start the WebSocket server.
#     """
#     logging.basicConfig(level=logging.INFO)
#     async with websockets.serve(handle_connection, "192.168.1.5", 8765):
#         logging.info("WebSocket server started on ws://192.168.1.5:8765")
#         await asyncio.Future()  # Keep the server running
