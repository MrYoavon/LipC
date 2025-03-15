# utils/auth.py
import json
import logging
from .state import clients

async def handle_authentication(websocket, data):
    """
    Authenticate a client.
    """
    username = data.get("username")
    password = data.get("password")
    # Placeholder authentication logic.
    if username and password:
        clients[username] = {"ws": websocket, "pc": None}
        await websocket.send(json.dumps({"type": "authenticate", "success": True}))
        logging.info(f"User '{username}' authenticated.")
    else:
        await websocket.send(json.dumps({"type": "authenticate", "success": False}))


# # utils/auth.py
# import json
# import logging
# import bcrypt
# from database.users import create_user, get_user
# from .state import clients

# async def handle_authentication(websocket, data):
#     """
#     Authenticate a client.
#     """
#     username = data.get("username")
#     password = data.get("password")
    
#     # Check that username and password are provided
#     if username and password:
#         # Properly hash the password
#         hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

#         # Example: Create or retrieve the user from the database.
#         # In a real-world scenario, check if the user already exists and then verify the hashed password.
#         user_data = {
#             "username": username,
#             "name": data.get("name", ""),
#             "password_hash": hashed_password.decode('utf-8'),
#             "profile_image": data.get("profile_image", "")
#         }
#         user_id = create_user(user_data)
#         clients[str(user_id)] = {"ws": websocket, "username": username, "pc": None}
        
#         await websocket.send(json.dumps({
#             "type": "authenticate", 
#             "success": True, 
#             "user_id": str(user_id)
#         }))
#         logging.info(f"User '{username}' authenticated with ID {user_id}.")
#     else:
#         await websocket.send(json.dumps({"type": "authenticate", "success": False}))
