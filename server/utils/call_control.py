# utils/call_control.py
import json
import logging
from .state import clients

async def handle_call_invite(websocket, data):
    """
    Forward a call invitation from the caller to the target (callee).
    Data should contain "from" (caller) and "target" (callee).
    """
    caller = data.get("from")
    target = data.get("target")
    logging.info(f"Call invite from {caller} to {target}")
    
    if target in clients:
        target_ws = clients[target]["ws"]
        invite_msg = {
            "type": "call_invite",
            "from": caller,
            "target": target
        }
        await target_ws.send(json.dumps(invite_msg))
    else:
        # Inform caller that the target isn't available.
        error_msg = {
            "type": "call_invite_response",
            "success": False,
            "message": "Target not connected."
        }
        await websocket.send(json.dumps(error_msg))

async def handle_call_accept(websocket, data):
    """
    Forward a call acceptance from the target (callee) back to the caller.
    Data should contain "from" (callee) and "target" (caller).
    """
    callee = data.get("from")
    caller = data.get("target")
    logging.info(f"Call accepted by {callee} for call from {caller}")
    
    if caller in clients:
        caller_ws = clients[caller]["ws"]
        accept_msg = {
            "type": "call_accept",
            "from": callee,
            "target": caller,
            "success": True
        }
        await caller_ws.send(json.dumps(accept_msg))
    else:
        error_msg = {
            "type": "call_accept",
            "success": False,
            "message": "Caller not connected."
        }
        await websocket.send(json.dumps(error_msg))

async def handle_call_reject(websocket, data):
    """
    Forward a call rejection from the target (callee) back to the caller.
    Data should contain "from" (callee) and "target" (caller).
    """
    callee = data.get("from")
    caller = data.get("target")
    logging.info(f"Call rejected by {callee} for call from {caller}")
    
    if caller in clients:
        caller_ws = clients[caller]["ws"]
        reject_msg = {
            "type": "call_reject",
            "from": callee,
            "target": caller,
            "success": False,
            "message": "Call rejected by callee."
        }
        await caller_ws.send(json.dumps(reject_msg))
    else:
        error_msg = {
            "type": "call_reject",
            "success": False,
            "message": "Caller not connected."
        }
        await websocket.send(json.dumps(error_msg))
