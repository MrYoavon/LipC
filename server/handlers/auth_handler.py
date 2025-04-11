# handlers/auth_handler.py
import json
import logging
import bcrypt
from database.users import create_user, get_user_by_username
from services.state import clients
from services.crypto_utils import send_encrypted

async def handle_authentication(websocket, data, aes_key):
    """
    Authenticate a client.
    """
    username = data.get("username")
    password = data.get("password")
    
    if username and password:
        # Retrieve the user from the database.
        potential_user = get_user_by_username(username)
        if potential_user:
            # Verify the hashed password.
            if bcrypt.checkpw(password.encode('utf-8'), potential_user["password_hash"].encode('utf-8')):
                # Save the session data.
                clients[str(potential_user["_id"])] = {"ws": websocket, "username": username, "aes_key": aes_key, "pc": None}
                logging.info(f"User '{username}' authenticated with ID {potential_user['_id']}.")
                logging.info(f"{potential_user.get('name', '')} | {potential_user.get('profile_pic', '')}")
                response = {
                    "type": "authenticate", 
                    "success": True, 
                    "user_id": str(potential_user["_id"]),
                    "name": potential_user.get("name", ""),
                    "profile_pic": potential_user.get("profile_pic", ""),
                }
                await send_encrypted(websocket, json.dumps(response), aes_key)
            else:
                logging.info(f"User '{username}' authentication failed (incorrect password).")
                response = {
                    "type": "authenticate",
                    "success": False,
                    "reason": "Incorrect password."
                }
                await send_encrypted(websocket, json.dumps(response), aes_key)
        else:
            logging.info(f"User '{username}' does not exist.")
            response = {
                "type": "authenticate",
                "success": False,
                "reason": "User does not exist."
            }
            await send_encrypted(websocket, json.dumps(response), aes_key)
    else:
        response = {
            "type": "authenticate",
            "success": False,
            "reason": "Username and password are required."
        }
        await send_encrypted(websocket, json.dumps(response), aes_key)


async def handle_signup(websocket, data, aes_key):
    """
    Register a new user.
    """
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        response = {
            "type": "signup",
            "success": False,
            "reason": "Username and password are required."
        }
        await send_encrypted(websocket, json.dumps(response), aes_key)
        return

    # Check if the username is already taken.
    if get_user_by_username(username):
        response = {
            "type": "signup",
            "success": False,
            "reason": "Username already exists."
        }
        await send_encrypted(websocket, json.dumps(response), aes_key)
        return

    # Hash the password before storing.
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Create the new user document.
    user_data = {
        "username": username,
        "password_hash": hashed_password,
        "name": data.get("name", ""),
        "profile_pic": data.get("profile_pic", ""),
        "contacts": []  # This will store ObjectIds of contacts.
    }
    user_id = create_user(user_data)
    
    clients[str(user_id)] = {"ws": websocket, "username": username, "pc": None}
    logging.info(f"New user '{username}' registered with ID {user_id}.")
    
    response = {
        "type": "signup",
        "success": True,
        "user_id": str(user_id)
    }
    await send_encrypted(websocket, json.dumps(response), aes_key)
