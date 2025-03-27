# # utils/auth.py
# import json
# import logging
# from .state import clients

# async def handle_authentication(websocket, data):
#     """
#     Authenticate a client.
#     """
#     username = data.get("username")
#     password = data.get("password")
#     # Placeholder authentication logic.
#     if username and password:
#         clients[username] = {"ws": websocket, "pc": None}
#         await websocket.send(json.dumps({"type": "authenticate", "success": True}))
#         logging.info(f"User '{username}' authenticated.")
#     else:
#         await websocket.send(json.dumps({"type": "authenticate", "success": False}))


# utils/auth.py
import json
import logging
import bcrypt
from database.users import create_user, get_user_by_username
from services.state import clients

async def handle_authentication(websocket, data):
    """
    Authenticate a client.
    """
    username = data.get("username")
    password = data.get("password")
    
    # Check that username and password are provided
    if username and password:
        # Retrieve the user from the database.
        potential_user = get_user_by_username(username)

        if potential_user:
            # If the user already exists, verify the hashed password.
            if bcrypt.checkpw(password.encode('utf-8'), potential_user["password_hash"].encode('utf-8')):
                clients[str(potential_user["_id"])] = {"ws": websocket, "username": username, "pc": None}
                logging.info(f"User '{username}' authenticated with ID {potential_user['_id']}.")
                logging.info(f"{potential_user.get('name', "")} | {potential_user.get('profile_pic', "")}")
                await websocket.send(json.dumps({
                    "type": "authenticate", 
                    "success": True, 
                    "user_id": str(potential_user["_id"]),
                    "name": potential_user.get("name", ""),
                    "profile_pic": potential_user.get("profile_pic", ""),
                }))
            else:
                logging.info(f"User '{username}' authentication failed.")
                await websocket.send(json.dumps({
                    "type": "authenticate",
                    "success": False,
                    "reason": "Incorrect password."
                }))
        else:
            logging.info(f"User '{username}' does not exist.")
            await websocket.send(json.dumps({
                "type": "authenticate",
                "success": False,
                "reason": "User does not exist."
            }))
    else:
        await websocket.send(json.dumps({"type": "authenticate", "success": False, "reason": "Username and password are required."}))


async def handle_signup(websocket, data):
    """
    Register a new user.
    """
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        await websocket.send(json.dumps({
            "type": "signup",
            "success": False,
            "reason": "Username and password are required."
        }))
        return

    # Check if the username is already taken.
    if get_user_by_username(username):
        await websocket.send(json.dumps({
            "type": "signup",
            "success": False,
            "reason": "Username already exists."
        }))
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
    
    # Respond with the new user ID.
    await websocket.send(json.dumps({
        "type": "signup",
        "success": True,
        "user_id": str(user_id)
    }))
