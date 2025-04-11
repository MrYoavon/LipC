# handlers/call_control.py
import json
import logging
from services.state import clients
from services.crypto_utils import send_encrypted

async def handle_call_invite(websocket, data, aes_key):
    """
    Forward a call invitation from the caller to the target (callee).
    Encrypts the message using the target's AES key if available.
    """
    caller = data.get("from")
    target = data.get("target")
    logging.info(f"Call invite from {caller} to {target}")
    
    if target in clients:
        target_ws = clients[target]["ws"]
        target_aes_key = clients[target].get("aes_key")
        logging.info(f"CALL INVITE: Target AES key: {target_aes_key}")
        if not target_aes_key:
            logging.warning(f"No AES key found for target {target}; falling back to sender's key.")
            target_aes_key = aes_key
        invite_msg = {
            "type": "call_invite",
            "from": caller,
            "target": target
        }
        await send_encrypted(target_ws, json.dumps(invite_msg), target_aes_key)
    else:
        # Inform the caller that the target isn't available.
        error_msg = {
            "type": "call_reject",
            "success": False,
            "message": f"{target} is not available."
        }
        await send_encrypted(websocket, json.dumps(error_msg), aes_key)

async def handle_call_accept(websocket, data, aes_key):
    """
    Forward a call acceptance from the target (callee) back to the caller.
    Encrypts the message using the caller's AES key if available.
    """
    callee = data.get("from")
    caller = data.get("target")
    logging.info(f"Call accepted by {callee} for call from {caller}")
    
    if caller in clients:
        caller_ws = clients[caller]["ws"]
        caller_aes_key = clients[caller].get("aes_key")
        if not caller_aes_key:
            logging.warning(f"No AES key found for caller {caller}; falling back to sender's key.")
            caller_aes_key = aes_key
        accept_msg = {
            "type": "call_accept",
            "from": callee,
            "target": caller,
            "success": True
        }
        await send_encrypted(caller_ws, json.dumps(accept_msg), caller_aes_key)
    else:
        error_msg = {
            "type": "call_accept",
            "success": False,
            "message": f"{caller} not connected."
        }
        await send_encrypted(websocket, json.dumps(error_msg), aes_key)

async def handle_call_reject(websocket, data, aes_key):
    """
    Forward a call rejection from the target (callee) back to the caller.
    Encrypts the message using the caller's AES key if available.
    """
    callee = data.get("from")
    caller = data.get("target")
    logging.info(f"Call rejected by {callee} for call from {caller}")
    
    if caller in clients:
        caller_ws = clients[caller]["ws"]
        caller_aes_key = clients[caller].get("aes_key")
        if not caller_aes_key:
            logging.warning(f"No AES key found for caller {caller}; falling back to sender's key.")
            caller_aes_key = aes_key
        reject_msg = {
            "type": "call_reject",
            "from": callee,
            "target": caller,
            "success": False,
            "message": f"Call rejected by {callee}."
        }
        await send_encrypted(caller_ws, json.dumps(reject_msg), caller_aes_key)
    else:
        error_msg = {
            "type": "call_reject",
            "success": False,
            "message": f"{caller} not connected."
        }
        await send_encrypted(websocket, json.dumps(error_msg), aes_key)

async def handle_call_end(websocket, data, aes_key):
    """
    Forward a call end request from either party to the other.
    Encrypts the message using the target's AES key if available.
    """
    sender = data.get("from")
    target = data.get("target")
    logging.info(f"Call end request from {sender} to {target}")
    
    if target in clients:
        target_ws = clients[target]["ws"]
        target_aes_key = clients[target].get("aes_key")
        if not target_aes_key:
            logging.warning(f"No AES key found for target {target}; falling back to sender's key.")
            target_aes_key = aes_key
        end_msg = {
            "type": "call_end",
            "from": sender,
            "target": target
        }
        await send_encrypted(target_ws, json.dumps(end_msg), target_aes_key)
    else:
        error_msg = {
            "type": "call_end",
            "success": False,
            "message": f"{target} not connected."
        }
        await send_encrypted(websocket, json.dumps(error_msg), aes_key)

async def handle_video_state(websocket, data, aes_key):
    """
    Forward video state updates between caller and target.
    Encrypts the message using the target's AES key if available.
    """
    sender = data.get("from")
    target = data.get("target")
    video_state = data.get("video")
    logging.info(f"Video state update from {sender} to {target}: {video_state}")
    
    if target in clients:
        target_ws = clients[target]["ws"]
        target_aes_key = clients[target].get("aes_key")
        if not target_aes_key:
            logging.warning(f"No AES key found for target {target}; falling back to sender's key.")
            target_aes_key = aes_key
        state_msg = {
            "type": "video_state",
            "success": True,
            "from": sender,
            "video": video_state
        }
        await send_encrypted(target_ws, json.dumps(state_msg), target_aes_key)
    else:
        error_msg = {
            "type": "video_state",
            "success": False,
            "message": f"{target} not connected."
        }
        await send_encrypted(websocket, json.dumps(error_msg), aes_key)
