# handlers/call_handler.py
import logging
from services.jwt_utils import verify_jwt_in_message
from services.state import clients
from services.crypto_utils import structure_encrypt_send_message, send_error_message

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _get_client_key(target, fallback_key):
    """Retrieve target's WebSocket and AES key, fallback if missing."""
    info = clients.get(target)
    if not info:
        return None, None
    return info["ws"], info.get("aes_key", fallback_key)


async def _validate_jwt(ws, data, aes_key, msg_type):
    """Verify JWT and extract user_id; send error on failure."""
    user_id = data.get("user_id")
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logger.warning(
            f"Invalid JWT for {msg_type}, user {user_id}: {result}")
        await send_error_message(ws, aes_key, msg_type, result.get("error"), result.get("message"))
        return None
    return data.get("payload", {})

# -----------------------------------------------------------------------------
# Call Control Handlers
# -----------------------------------------------------------------------------


async def handle_call_invite(websocket, data, aes_key):
    """Forward call invite to the target user."""
    payload = await _validate_jwt(websocket, data, aes_key, "call_invite")
    if payload is None:
        return
    caller, target = payload.get("from"), payload.get("target")
    logger.info(f"Call invite from {caller} to {target}")

    target_ws, target_key = _get_client_key(target, aes_key)
    if target_ws:
        await structure_encrypt_send_message(
            websocket=target_ws,
            aes_key=target_key,
            msg_type="call_invite",
            success=True,
            payload={"from": caller, "target": target},
        )
    else:
        await send_error_message(
            websocket, aes_key, "call_invite",
            "TARGET_NOT_AVAILABLE", f"{target} is not available."
        )


async def handle_call_accept(websocket, data, aes_key):
    """Forward call acceptance back to the caller."""
    payload = await _validate_jwt(websocket, data, aes_key, "call_accept")
    if payload is None:
        return
    callee, caller = payload.get("from"), payload.get("target")
    logger.info(f"Call accepted by {callee} for {caller}")

    caller_ws, caller_key = _get_client_key(caller, aes_key)
    if caller_ws:
        await structure_encrypt_send_message(
            websocket=caller_ws,
            aes_key=caller_key,
            msg_type="call_accept",
            success=True,
            payload={"from": callee, "target": caller},
        )
    else:
        await send_error_message(
            websocket, aes_key, "call_accept",
            "CALLER_NOT_AVAILABLE", f"{caller} not connected."
        )


async def handle_call_reject(websocket, data, aes_key):
    """Forward call rejection back to the caller."""
    payload = await _validate_jwt(websocket, data, aes_key, "call_reject")
    if payload is None:
        return
    callee, caller = payload.get("from"), payload.get("target")
    logger.info(f"Call rejected by {callee} for {caller}")

    caller_ws, caller_key = _get_client_key(caller, aes_key)
    if caller_ws:
        await structure_encrypt_send_message(
            websocket=caller_ws,
            aes_key=caller_key,
            msg_type="call_reject",
            success=False,
            payload={"from": callee, "target": caller,
                     "message": f"Call rejected by {callee}."},
        )
    else:
        await send_error_message(
            websocket, aes_key, "call_reject",
            "CALLER_NOT_AVAILABLE", f"{caller} not connected."
        )


async def handle_call_end(websocket, data, aes_key):
    """Forward call end notification between users."""
    payload = await _validate_jwt(websocket, data, aes_key, "call_end")
    if payload is None:
        return
    sender, target = payload.get("from"), payload.get("target")
    logger.info(f"Call end request from {sender} to {target}")

    target_ws, target_key = _get_client_key(target, aes_key)
    if target_ws:
        await structure_encrypt_send_message(
            websocket=target_ws,
            aes_key=target_key,
            msg_type="call_end",
            success=True,
            payload={"from": sender, "target": target},
        )
    else:
        await send_error_message(
            websocket, aes_key, "call_end",
            "TARGET_NOT_AVAILABLE", f"{target} not connected."
        )


async def handle_video_state(websocket, data, aes_key):
    """Forward video state changes to the other party."""
    payload = await _validate_jwt(websocket, data, aes_key, "video_state")
    if payload is None:
        return
    sender, target, state = payload.get(
        "from"), payload.get("target"), payload.get("video")
    logger.info(f"Video state update from {sender} to {target}: {state}")

    target_ws, target_key = _get_client_key(target, aes_key)
    if target_ws:
        await structure_encrypt_send_message(
            websocket=target_ws,
            aes_key=target_key,
            msg_type="video_state",
            success=True,
            payload={"from": sender, "video": state},
        )
    else:
        await send_error_message(
            websocket, aes_key, "video_state",
            "TARGET_NOT_AVAILABLE", f"{target} not connected."
        )


async def handle_set_model_preference(websocket, data, aes_key):
    """Update the user’s server-side model preference."""
    payload = await _validate_jwt(websocket, data, aes_key, "set_model_preference")
    if payload is None:
        return
    user = data.get("user_id")
    model = payload.get("model_type", "lip")

    if user not in clients:
        await send_error_message(
            websocket, aes_key, "set_model_preference",
            "USER_NOT_FOUND", f"{user} not connected."
        )
        return

    clients[user]["model_type"] = model
    logger.info(f"Set model preference for {user} to {model}")
    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type="set_model_preference",
        success=True,
        payload={"model_type": model},
    )
