# handlers/connection.py

import asyncio
import base64
import json
import logging
import os
import time

# Local handlers
from handlers.auth_handler import handle_authentication, handle_signup, handle_token_refresh
from handlers.contacts_handler import handle_get_contacts, handle_add_contact
from handlers.call_handler import (
    handle_call_invite, handle_call_accept, handle_call_reject,
    handle_call_end, handle_set_model_preference, handle_video_state
)
from handlers.signaling_handler import handle_offer, handle_answer, handle_ice_candidate
from handlers.call_history_handler import handle_fetch_call_history

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
RATE_LIMITER = RateLimiter()

# Mapping of message types to handler functions
HANDLERS = {
    "authenticate": handle_authentication,
    "signup":       handle_signup,
    "refresh_token": handle_token_refresh,
    "get_contacts": handle_get_contacts,
    "add_contact":  handle_add_contact,
    "call_invite":  handle_call_invite,
    "call_accept":  handle_call_accept,
    "call_reject":  handle_call_reject,
    "call_end":     handle_call_end,
    "video_state":  handle_video_state,
    "offer":        handle_offer,
    "answer":       handle_answer,
    "ice_candidate": handle_ice_candidate,
    "fetch_call_history": handle_fetch_call_history,
    "set_model_preference": handle_set_model_preference,
}

# -----------------------------------------------------------------------------
# Helper Coroutines
# -----------------------------------------------------------------------------


async def _perform_handshake(ws) -> bytes:
    """
    Perform ECDH handshake over WebSocket to derive AES key.
    """
    priv, pub = generate_ephemeral_key()
    pub_ser = base64.b64encode(serialize_public_key(pub)).decode()
    salt = base64.b64encode(os.urandom(16)).decode()

    # Send server public key and salt
    await ws.send(json.dumps({
        "msg_type": "handshake",
        "payload": {"server_public_key": pub_ser, "salt": salt}
    }))

    # Receive client handshake
    data = json.loads(await ws.recv())
    if data.get("msg_type") != "handshake":
        raise ValueError("Invalid handshake response")
    client_pub = base64.b64decode(data["payload"]["client_public_key"])
    client_pub = deserialize_public_key(client_pub)

    # Derive AES key
    secret = compute_shared_secret(priv, client_pub)
    return derive_aes_key(secret, salt=salt.encode())


async def _heartbeat(ws, last_ping_ref):
    """
    Periodically check the last ping time and close if timed out.
    """
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        if time.time() - last_ping_ref[0] > HEARTBEAT_TIMEOUT:
            logging.warning("Heartbeat timeout, closing connection")
            await ws.close()
            break


async def _decrypt_and_parse(raw_message, aes_key):
    """
    Attempt decryption; fallback to plaintext JSON.
    """
    data = json.loads(raw_message)
    if all(k in data for k in ("nonce", "ciphertext", "tag")):
        nonce = base64.b64decode(data["nonce"])
        ct = base64.b64decode(data["ciphertext"])
        tag = base64.b64decode(data["tag"])
        plain = decrypt_message(aes_key, nonce, ct, tag)
        return json.loads(plain.decode())
    return data


async def _dispatch(ws, data, aes_key):
    """
    Route a parsed message to its handler.
    """
    msg_type = data.get("msg_type")
    if msg_type == "ping":
        return {"pong": True}

    handler = HANDLERS.get(msg_type)
    if handler:
        return await handler(ws, data, aes_key)

    # Unknown
    logging.warning(f"Unknown msg_type: {msg_type}")
    await send_encrypted(ws, json.dumps({"error": "Unknown message type"}), aes_key)


async def _cleanup(ws):
    """
    Close PeerConnection if exists, remove client, and reset rate limiter.
    """
    for user, info in list(clients.items()):
        if info.get("ws") == ws:
            pc = info.get("pc")
            if pc:
                await pc.close()
            del clients[user]
            break
    ip = (ws.remote_address[0] if ws.remote_address else None)
    if not RATE_LIMITER.is_banned(ip) and ip is not None:
        RATE_LIMITER.forget(ip)

# -----------------------------------------------------------------------------
# Main Connection Handler
# -----------------------------------------------------------------------------


async def handle_connection(ws):
    """
    Orchestrate handshake, heartbeat, rate-limit, decrypt/dispatch loop, and cleanup.
    """
    logging.info("New connection")
    ip = ws.remote_address[0]
    last_ping = [time.time()]

    # Start heartbeat monitor
    hb = asyncio.create_task(_heartbeat(ws, last_ping))

    try:
        aes_key = await _perform_handshake(ws)
    except Exception as e:
        logging.error("Handshake failed", exc_info=e)
        await ws.send(json.dumps({"error": "Handshake failed"}))
        return

    try:
        async for raw in ws:
            # Rate limit
            if not RATE_LIMITER.allow(ip):
                logging.warning("Rate limit exceeded")
                await ws.close(code=4008, reason="Rate limit exceeded")
                break

            try:
                data = await _decrypt_and_parse(raw, aes_key)
            except Exception as e:
                logging.error("Decrypt/parse error", exc_info=e)
                await send_encrypted(ws, json.dumps({"error": "Invalid message format"}), aes_key)
                continue

            # Heartbeat
            if data.get("msg_type") == "ping":
                last_ping[0] = time.time()
                await send_encrypted(ws, json.dumps({"msg_type": "pong"}), aes_key)
                continue

            await _dispatch(ws, data, aes_key)

    except Exception as e:
        logging.error("Connection loop error", exc_info=e)
    finally:
        hb.cancel()
        await _cleanup(ws)

# -----------------------------------------------------------------------------
# Disconnection Cleanup (if separate)
# -----------------------------------------------------------------------------


async def handle_disconnection(ws):
    await _cleanup(ws)
