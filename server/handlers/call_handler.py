# handlers/call_control.py
import logging
from services.jwt_utils import verify_jwt_in_message
from services.state import clients
from services.crypto_utils import structure_encrypt_send_message


async def handle_call_invite(websocket, data, aes_key):
    """
    Forward a call invitation from the caller to the target (callee).
    Encrypts the message using the target's AES key if available.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    caller = payload.get("from")
    target = payload.get("target")

    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_invite",
            success=False,
            error_code=result["error"],
            error_message=result["message"],
        )
        return

    logging.info(f"Call invite from {caller} to {target}")

    if target in clients:
        target_ws = clients[target]["ws"]
        target_aes_key = clients[target].get("aes_key")
        logging.info(f"CALL INVITE: Target AES key: {target_aes_key}")
        if not target_aes_key:
            logging.warning(
                f"No AES key found for target {target}; falling back to sender's key.")
            target_aes_key = aes_key
        invite_data = {
            "from": caller,
            "target": target
        }
        await structure_encrypt_send_message(
            websocket=target_ws,
            aes_key=target_aes_key,
            msg_type="call_invite",
            success=True,
            payload=invite_data
        )
    else:
        # Inform the caller that the target isn't available.
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_invite",
            success=False,
            error_code="TARGET_NOT_AVAILABLE",
            error_message=f"{target} is not available."
        )


async def handle_call_accept(websocket, data, aes_key):
    """
    Forward a call acceptance from the target (callee) back to the caller.
    Encrypts the message using the caller's AES key if available.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    callee = payload.get("from")
    caller = payload.get("target")

    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_accept",
            success=False,
            error_code=result["error"],
            error_message=result["message"]
        )
        return

    logging.info(f"Call accepted by {callee} for call from {caller}")

    if caller in clients:
        caller_ws = clients[caller]["ws"]
        caller_aes_key = clients[caller].get("aes_key")
        if not caller_aes_key:
            logging.warning(
                f"No AES key found for caller {caller}; falling back to sender's key.")
            caller_aes_key = aes_key
        accept_data = {
            "from": callee,
            "target": caller,
        }
        await structure_encrypt_send_message(
            websocket=caller_ws,
            aes_key=caller_aes_key,
            msg_type="call_accept",
            success=True,
            payload=accept_data
        )
    else:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_accept",
            success=False,
            error_code="CALLER_NOT_AVAILABLE",
            error_message=f"{caller} not connected."
        )


async def handle_call_reject(websocket, data, aes_key):
    """
    Forward a call rejection from the target (callee) back to the caller.
    Encrypts the message using the caller's AES key if available.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    callee = payload.get("from")
    caller = payload.get("target")

    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_reject",
            success=False,
            error_code=result["error"],
            error_message=result["message"]
        )
        return

    logging.info(f"Call rejected by {callee} for call from {caller}")

    if caller in clients:
        caller_ws = clients[caller]["ws"]
        caller_aes_key = clients[caller].get("aes_key")
        if not caller_aes_key:
            logging.warning(
                f"No AES key found for caller {caller}; falling back to sender's key.")
            caller_aes_key = aes_key
        reject_data = {
            "from": callee,
            "target": caller,
            "message": f"Call rejected by {callee}."
        }
        await structure_encrypt_send_message(
            websocket=caller_ws,
            aes_key=caller_aes_key,
            msg_type="call_reject",
            success=False,
            payload=reject_data
        )
    else:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_reject",
            success=False,
            error_code="CALLER_NOT_AVAILABLE",
            error_message=f"{caller} not connected."
        )


async def handle_call_end(websocket, data, aes_key):
    """
    Forward a call end request from either party to the other.
    Encrypts the message using the target's AES key if available.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    target = payload.get("target")

    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_end",
            success=False,
            error_code=result["error"],
            error_message=result["message"]
        )
        return

    logging.info(f"Call end request from {sender} to {target}")

    if target in clients:
        target_ws = clients[target]["ws"]
        target_aes_key = clients[target].get("aes_key")
        if not target_aes_key:
            logging.warning(
                f"No AES key found for target {target}; falling back to sender's key.")
            target_aes_key = aes_key
        end_data = {
            "from": sender,
            "target": target
        }
        await structure_encrypt_send_message(
            websocket=target_ws,
            aes_key=target_aes_key,
            msg_type="call_end",
            success=True,
            payload=end_data
        )
    else:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="call_end",
            success=False,
            error_code="TARGET_NOT_AVAILABLE",
            error_message=f"{target} not connected."
        )


async def handle_video_state(websocket, data, aes_key):
    """
    Forward video state updates between caller and target.
    Encrypts the message using the target's AES key if available.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    target = payload.get("target")
    video_state = payload.get("video")

    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for user {user_id}: {result}")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="video_state",
            success=False,
            error_code=result["error"],
            error_message=result["message"]
        )
        return

    logging.info(
        f"Video state update from {sender} to {target}: {video_state}")

    if target in clients:
        target_ws = clients[target]["ws"]
        target_aes_key = clients[target].get("aes_key")
        if not target_aes_key:
            logging.warning(
                f"No AES key found for target {target}; falling back to sender's key.")
            target_aes_key = aes_key
        state_data = {
            "from": sender,
            "video": video_state
        }
        await structure_encrypt_send_message(
            websocket=target_ws,
            aes_key=target_aes_key,
            msg_type="video_state",
            success=True,
            payload=state_data
        )
    else:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="video_state",
            success=False,
            error_code="TARGET_NOT_AVAILABLE",
            error_message=f"{target} not connected."
        )
