# handlers/connection.py

import asyncio
import base64
import json
import logging
import os
import time
import traceback

from services.state import clients
from handlers.auth_handler import handle_authentication, handle_signup, handle_token_refresh
from handlers.contacts_handler import handle_get_contacts, handle_add_contact
from handlers.call_handler import (
    handle_call_invite, handle_call_accept, handle_call_reject,
    handle_call_end, handle_video_state
)
from handlers.signaling_handler import handle_offer, handle_answer, handle_ice_candidate
from handlers.call_history_handler import handle_log_call, handle_fetch_call_history

# Import crypto utilities for key generation, encryption, decryption, and AES key derivation.
from services.crypto_utils import (
    generate_ephemeral_key,
    serialize_public_key,
    deserialize_public_key,
    compute_shared_secret,
    derive_aes_key,
    send_encrypted,
    decrypt_message
)

async def dispatch_message_encrypted(websocket, data, aes_key):
    """
    Dispatch a decrypted message (in dict form) to the appropriate handler.
    The handlers are modified to accept an extra 'aes_key' argument so that any responses
    sent back to the client are also encrypted.
    """
    try:
        logging.info(f"Dispatching message: {data}")
        # Retrieve the message type from the data.
        message_type = data.get("msg_type")
        # Based on message type, call the associated handler.
        if message_type == "authenticate":
            await handle_authentication(websocket, data, aes_key)
        elif message_type == "signup":
            await handle_signup(websocket, data, aes_key)
        elif message_type == "refresh_token":
            await handle_token_refresh(websocket, data, aes_key)
        elif message_type == "get_contacts":
            await handle_get_contacts(websocket, data, aes_key)
        elif message_type == "add_contact":
            await handle_add_contact(websocket, data, aes_key)
        elif message_type == "call_invite":
            await handle_call_invite(websocket, data, aes_key)
        elif message_type == "call_accept":
            await handle_call_accept(websocket, data, aes_key)
        elif message_type == "call_reject":
            await handle_call_reject(websocket, data, aes_key)
        elif message_type == "call_end":
            await handle_call_end(websocket, data, aes_key)
        elif message_type == "video_state":
            await handle_video_state(websocket, data, aes_key)
        elif message_type == "offer":
            await handle_offer(websocket, data, aes_key)
        elif message_type == "answer":
            await handle_answer(websocket, data, aes_key)
        elif message_type == "ice_candidate":
            await handle_ice_candidate(websocket, data, aes_key)
        elif message_type == "log_call":
            await handle_log_call(websocket, data, aes_key)
        elif message_type == "fetch_call_history":
            await handle_fetch_call_history(websocket, data, aes_key)
        else:
            # Unknown message type - log a warning and send an error response back.
            logging.warning(f"Unknown message type: {message_type}")
            await send_encrypted(websocket, json.dumps({"error": "Unknown message type"}), aes_key)
    except Exception as e:
        # Log any error that occurs during the dispatch.
        logging.error("Error in dispatch: " + str(e))
        await send_encrypted(websocket, json.dumps({"error": "Dispatch error"}), aes_key)

async def handle_connection(websocket):
    """
    Handle a new WebSocket connection, including a secure encryption handshake and
    periodic heartbeat checking to ensure the client is still connected.
    """
    logging.info("New connection established.")
    last_ping = time.time()  # Tracks the time of the last received ping.

    async def heartbeat_check():
        """Periodically verify that a heartbeat (ping) was recently received."""
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds.
            if time.time() - last_ping > 15:
                # If no ping has been received in the last 15 seconds, close the connection.
                logging.warning("No ping received from client in threshold; closing connection.")
                await websocket.close()
                break

    # Start the heartbeat checking task concurrently.
    heartbeat_task = asyncio.create_task(heartbeat_check())

    # --- Encryption Handshake Phase ---
    try:
        # 1. Generate server ephemeral key pair.
        server_private, server_public = generate_ephemeral_key()
        # Serialize the server's public key using base64-encoded format.
        server_pub_serialized = base64.b64encode(serialize_public_key(server_public)).decode('utf-8')
        # Generate a unique salt (128-bit) for AES key derivation.
        salt = base64.b64encode(os.urandom(16)).decode('utf-8')

        # 2. Prepare the handshake message to share the public key and salt with the client.
        handshake_message = json.dumps({
            "msg_type": "handshake",
            "payload" : {
                "server_public_key": server_pub_serialized,
                "salt": salt,
            }
        })
        # Send the handshake message over the WebSocket connection.
        await websocket.send(handshake_message)
        logging.info("Sent handshake message to client.")

        # 3. Wait for the client's handshake response.
        client_handshake = await websocket.recv()
        handshake_data = json.loads(client_handshake)
        handshake_payload = handshake_data.get("payload")
        # Validate that the handshake response contains the required fields.
        if handshake_data.get("msg_type") != "handshake" or "client_public_key" not in handshake_payload:
            await websocket.send(json.dumps({"error": "Invalid handshake response"}))
            logging.error("Invalid handshake response received.")
            return
        
        # Deserialize the client's public key from its base64 encoded string.
        client_pub_serialized = base64.b64decode(handshake_payload["client_public_key"])
        client_public = deserialize_public_key(client_pub_serialized)

        # 4. Compute the shared secret using the server's private key and client's public key,
        # then derive the AES key for encryption/decryption using the shared secret and salt.
        shared_secret = compute_shared_secret(server_private, client_public)
        aes_key = derive_aes_key(shared_secret, salt=salt.encode('utf-8'))
        logging.info(f"Secure session established with encryption handshake.")
    except Exception as e:
        # In case of any error during the handshake, log the error and notify the client.
        logging.error("Encryption handshake failed: " + str(e))
        await websocket.send(json.dumps({"error": "Handshake failed"}))
        return

    # --- Encrypted Communication Phase ---
    try:
        # Listen for incoming messages on the WebSocket.
        async for raw_message in websocket:
            try:
                # Try to interpret each message as an encrypted JSON object.
                encrypted_payload = json.loads(raw_message)
                # Check if the message contains encryption metadata.
                if all(k in encrypted_payload for k in ("nonce", "ciphertext", "tag")):
                    nonce = base64.b64decode(encrypted_payload['nonce'])
                    ciphertext = base64.b64decode(encrypted_payload['ciphertext'])
                    tag = base64.b64decode(encrypted_payload['tag'])
                    # Decrypt the message using the derived AES key.
                    decrypted_bytes = decrypt_message(aes_key, nonce, ciphertext, tag)
                    decrypted_text = decrypted_bytes.decode('utf-8')
                    data = json.loads(decrypted_text)
                else:
                    # If not in the expected encrypted format, try to parse as plaintext.
                    data = json.loads(raw_message)
            except Exception as e:
                # Log decryption errors and send an error response back to the client.
                logging.error("Failed to decrypt or decode message: " + str(e))
                await send_encrypted(websocket, json.dumps({"error": "Invalid encrypted message format"}), aes_key)
                continue

            # Process heartbeat pings to update the last_ping timestamp.
            if data.get("msg_type") == "ping":
                last_ping = time.time()
                await send_encrypted(websocket, json.dumps({"msg_type": "pong"}), aes_key)
            else:
                # For all other message types, dispatch to the appropriate handler.
                await dispatch_message_encrypted(websocket, data, aes_key)
    except Exception as e:
        # Log and print any connection errors.
        logging.error(f"Connection error: {e}\n{traceback.format_exc()}")
    finally:
        # Cancel the heartbeat task and cleanup resources.
        heartbeat_task.cancel()
        await handle_disconnection(websocket)

async def handle_disconnection(websocket):
    """
    Cleanup the state when a client disconnects.
    This function:
      - Finds the disconnected client in the clients dictionary.
      - Closes any associated PeerConnection if it exists.
      - Removes the client from the active clients list.
    """
    disconnected_username = None
    # Iterate over connected clients to find the matching WebSocket.
    for username, info in list(clients.items()):
        if info["ws"] == websocket:
            # If a PeerConnection exists, close it.
            if info.get("pc"):
                await info["pc"].close()
            disconnected_username = username
            break
    # If a disconnected user was found, log the disconnection and remove from clients.
    if disconnected_username:
        logging.info(f"User {disconnected_username} disconnected.")
        del clients[disconnected_username]
