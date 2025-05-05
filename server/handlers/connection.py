# handlers/connection.py

import asyncio
import base64
import json
import logging
import os
import time

import websockets

# Local handlers
from handlers.auth_handler import AuthHandler
from handlers.contacts_handler import ContactsHandler
from handlers.call_handler import CallHandler
from handlers.signaling_handler import SignalingHandler
from handlers.call_history_handler import CallHistoryHandler

# Crypto and rate limiting
from services.crypto_utils import (
    generate_ephemeral_key, serialize_public_key, deserialize_public_key,
    compute_shared_secret, derive_aes_key, send_encrypted, decrypt_message
)
from services.rate_limiter import RateLimiter
from services.state import clients

from constants import HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT

# -----------------------------------------------------------------------------
# Configuration and Global Instances
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

RATE_LIMITER = RateLimiter()

# Instantiate handler classes
auth_handler = AuthHandler()
contacts_handler = ContactsHandler()
call_handler = CallHandler()
signaling_handler = SignalingHandler()
call_history_handler = CallHistoryHandler()

# Mapping of message types to handler functions
HANDLERS = {
    "authenticate":         auth_handler.handle_authentication,
    "signup":               auth_handler.handle_signup,
    "logout":               auth_handler.handle_logout,
    "refresh_token":        auth_handler.handle_refresh_token,
    "get_contacts":         contacts_handler.handle_get_contacts,
    "add_contact":          contacts_handler.handle_add_contact,
    "call_invite":          call_handler.handle_call_invite,
    "call_accept":          call_handler.handle_call_accept,
    "call_reject":          call_handler.handle_call_reject,
    "call_end":             call_handler.handle_call_end,
    "video_state":          call_handler.handle_video_state,
    "set_model_preference": call_handler.handle_set_model_preference,
    "offer":                signaling_handler.handle_offer,
    "answer":               signaling_handler.handle_answer,
    "ice_candidate":        signaling_handler.handle_ice_candidate,
    "fetch_call_history":   call_history_handler.handle_fetch_call_history,
}


class ConnectionHandler:
    """
    Manages a single WebSocket connection: handshake, heartbeat,
    decrypt/dispatch loop, cleanup and dispatches to all other handlers.
    """

    def __init__(self):
        """
        Initialize the ConnectionHandler with a WebSocket instance.
        """
        self.ws = None
        self.aes_key = None
        self.last_ping = time.time()

    async def handle_connection(self, ws):
        """
        Main entry point for handling a new WebSocket connection.

        Orchestrates the handshake, heartbeat monitoring, rate limiting,
        message decrypt/parse/dispatch loop, and final cleanup on disconnect.

        Parameters:
            ws (websockets.WebSocketServerProtocol): The WebSocket connection instance.

        Returns:
            None
        """
        logger.info("New connection")
        self.ws = ws
        ip = self.ws.remote_address[0]
        last_ping = [time.time()]

        # Start heartbeat monitor
        hb = asyncio.create_task(self._heartbeat())

        try:
            self.aes_key = await self._perform_handshake()
            logger.info("Handshake successful")
        except Exception as e:
            logger.error("Handshake failed", exc_info=e)
            await self.ws.send(json.dumps({"error": "Handshake failed"}))
            return

        try:
            async for raw in self.ws:
                # Rate limit
                if not RATE_LIMITER.allow(ip):
                    logger.warning("Rate limit exceeded")
                    await self.ws.close(code=4008, reason="Rate limit exceeded")
                    break

                try:
                    data = await self._decrypt_and_parse(raw)
                except Exception as e:
                    logger.error("Decrypt/parse error", exc_info=e)
                    await send_encrypted(self.ws, json.dumps({"error": "Invalid message format"}), self.aes_key)
                    continue

                # Heartbeat
                if data.get("msg_type") == "ping":
                    last_ping[0] = time.time()
                    await send_encrypted(self.ws, json.dumps({"msg_type": "pong"}), self.aes_key)
                    continue

                await self._dispatch(data)
        except websockets.exceptions.ConnectionClosedError as e:
            logger.info("Connection closed by client")
            hb.cancel()
            await self._cleanup()
        except Exception as e:
            logger.error("Connection loop error", exc_info=e)
        finally:
            hb.cancel()
            await self._cleanup()

    async def _perform_handshake(self) -> bytes:
        """
        Perform an Elliptic-curve Diffie Hellman (ECDH) handshake with the client.

        This coroutine generates a server private/public key pair, sends the public key
        and a random salt to the client, receives the client's public key, and derives
        a shared AES key for subsequent encrypted communication.

        Returns:
            aes_key (bytes): The derived AES key for encrypting/decrypting messages.

        Raises:
            ValueError: If the client response does not contain a valid handshake.
        """
        priv, pub = generate_ephemeral_key()
        pub_ser = base64.b64encode(serialize_public_key(pub)).decode()
        salt = base64.b64encode(os.urandom(16)).decode()

        # Send server public key and salt
        await self.ws.send(json.dumps({
            "msg_type": "handshake",
            "payload": {"server_public_key": pub_ser, "salt": salt}
        }))

        # Receive client handshake
        data = json.loads(await self.ws.recv())
        if data.get("msg_type") != "handshake":
            raise ValueError(
                f"Invalid handshake response | {data.get('msg_type')}")
        client_pub = base64.b64decode(data["payload"]["client_public_key"])
        client_pub = deserialize_public_key(client_pub)

        # Derive AES key
        secret = compute_shared_secret(priv, client_pub)
        return derive_aes_key(secret, salt=salt.encode())

    async def _heartbeat(self):
        """
        Monitor heartbeat pings from the client and close connection on timeout.

        Periodically checks if the time since the last ping exceeds a timeout threshold.
        If so, logs a warning and closes the WebSocket connection.

        Returns:
            None
        """
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if time.time() - self.last_ping[0] > HEARTBEAT_TIMEOUT:
                logger.warning("Heartbeat timeout, closing connection")
                await self.ws.close()
                break

    async def _decrypt_and_parse(self, raw_message):
        """
        Decrypt an incoming message if encrypted, or parse it as plaintext JSON.

        Checks for encryption fields (nonce, ciphertext, tag). If present,
        decrypts the payload using the provided AES key. Otherwise, returns the
        parsed JSON directly.

        Parameters:
            raw_message (str): The raw string message received over WebSocket.

        Returns:
            data (dict): The parsed JSON object after decryption or direct parse.
        """
        data = json.loads(raw_message)
        if all(k in data for k in ("nonce", "ciphertext", "tag")):
            nonce = base64.b64decode(data["nonce"])
            ct = base64.b64decode(data["ciphertext"])
            tag = base64.b64decode(data["tag"])
            plain = decrypt_message(self.aes_key, nonce, ct, tag)
            return json.loads(plain.decode())
        return data

    async def _dispatch(self, data):
        """
        Dispatch a parsed message to the appropriate handler based on its type.

        If the message is a ping, responds with a pong. Otherwise looks up
        the handler in HANDLERS mapping and invokes it. Unknown types result
        in an encrypted error response.

        Parameters:
            data (dict): The parsed message data.

        Returns:
            result: The return value of the handler coroutine, if any.
        """
        msg_type = data.get("msg_type")
        if msg_type == "ping":
            return {"pong": True}

        handler = HANDLERS.get(msg_type)
        if handler:
            return await handler(self.ws, data, self.aes_key)

        # Unknown
        logger.warning(f"Unknown msg_type: {msg_type}")
        await send_encrypted(self.ws, json.dumps({"error": "Unknown message type"}), self.aes_key)

    async def _cleanup(self):
        """
        Cleanup client state on connection close or error.

        Closes any active PeerConnection for the client, removes their entry from
        the clients dictionary, and resets rate limiter state for their IP if not banned.

        Returns:
            None
        """
        for user, info in list(clients.items()):
            if info.get("ws") == self.ws:
                pc = info.get("pc")
                if pc:
                    await pc.close()
                del clients[user]
                break
        ip = (self.ws.remote_address[0] if self.ws.remote_address else None)
        if not RATE_LIMITER.is_banned(ip) and ip is not None:
            RATE_LIMITER.forget(ip)
