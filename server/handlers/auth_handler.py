# handlers/auth_handler.py
import logging
import bcrypt
from database.users import create_user, get_user_by_id, get_user_by_username
from services.jwt_utils import (
    create_access_token,
    create_refresh_token,
    refresh_access_token,
    verify_jwt
)
from services.state import clients
from services.crypto_utils import structure_encrypt_send_message


async def handle_authentication(websocket, data, aes_key):
    """
    Authenticate a client using username and password.
    After successful authentication, generate and return a JWT access token
    (and a refresh token) to the client.
    """
    payload = data.get("payload")
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="authenticate",
            success=False,
            error_code="AUTH_MISSING_CREDENTIALS",
            error_message="Username and password are required."
        )
        return

    # Retrieve the user record from the database.
    potential_user = get_user_by_username(username)
    if potential_user:
        # Verify the provided password against the stored hash.
        if bcrypt.checkpw(password.encode('utf-8'), potential_user["password_hash"].encode('utf-8')):
            user_id = str(potential_user["_id"])
            # Generate JWT tokens after successful password verification.
            jwt_token = create_access_token(user_id)
            refresh_token = create_refresh_token(user_id)

            # Save session data for the connected client.
            clients[user_id] = {
                "ws": websocket, "username": username, "aes_key": aes_key, "pc": None}
            logging.info(f"User '{username}' authenticated with ID {user_id}.")

            response_data = {
                "user_id": user_id,
                "name": potential_user.get("name", ""),
                "profile_pic": potential_user.get("profile_pic", ""),
                "access_token": jwt_token,
                "refresh_token": refresh_token
            }
            await structure_encrypt_send_message(
                websocket=websocket,
                aes_key=aes_key,
                msg_type="authenticate",
                success=True,
                payload=response_data
            )
        else:
            logging.info(
                f"User '{username}' authentication failed (incorrect password).")
            await structure_encrypt_send_message(
                websocket=websocket,
                aes_key=aes_key,
                msg_type="authenticate",
                success=False,
                error_code="INCORRECT_PASSWORD",
                error_message="Incorrect password."
            )
    else:
        logging.info(f"User '{username}' does not exist.")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="authenticate",
            success=False,
            error_code="USER_NOT_FOUND",
            error_message="User does not exist."
        )


async def handle_signup(websocket, data, aes_key):
    """
    Register a new user.
    On success, generate and return a JWT access token (and a refresh token) along with basic user details.
    The structured response is encrypted and sent over the websocket.
    """
    payload = data.get("payload")
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="signup",
            success=False,
            error_code="SIGNUP_MISSING_CREDENTIALS",
            error_message="Username and password are required."
        )
        return

    # Check if the username is already taken.
    if get_user_by_username(username):
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="signup",
            success=False,
            error_code="USERNAME_EXISTS",
            error_message="Username already exists."
        )
        return

    # Hash the password before storing.
    hashed_password = bcrypt.hashpw(password.encode(
        'utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Create the new user document.
    user_data = {
        "username": username,
        "password_hash": hashed_password,
        "name": data.get("name", ""),
        "profile_pic": data.get("profile_pic", ""),
        "contacts": []  # This will store ObjectIds of contacts.
    }
    user_id = create_user(user_data)

    # Generate JWT tokens for the newly registered user.
    jwt_token = create_access_token(str(user_id))
    refresh_token = create_refresh_token(str(user_id))

    # Save session data for the connected client.
    clients[str(user_id)] = {"ws": websocket,
                             "username": username, "aes_key": aes_key, "pc": None}
    logging.info(f"New user '{username}' registered with ID {user_id}.")

    response_data = {
        "user_id": str(user_id),
        "access_token": jwt_token,
        "refresh_token": refresh_token
    }
    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type="signup",
        success=True,
        payload=response_data
    )


async def handle_token_refresh(websocket, data, aes_key):
    """
    Refresh a user's access token.
    Expects the incoming payload to contain the refresh token.
    On success, generates and returns a new access token.
    """
    payload = data.get("payload", {})
    refresh_token = payload.get("refresh_jwt")

    if not refresh_token:
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="refresh_token",
            success=False,
            error_code="MISSING_REFRESH_TOKEN",
            error_message="Refresh token is required."
        )
        return

    try:
        token_data = verify_jwt(refresh_token, expected_type="refresh")
        user_id = token_data.get("sub")
        logging.info(f"User ID: {user_id} | Refresh token: {refresh_token}")

        new_access_token = refresh_access_token(refresh_token)
        user_data = get_user_by_id(user_id)
        username = user_data.get("username", "")

        # Save session data for the connected client.
        clients[user_id] = {
            "ws": websocket, "username": username, "aes_key": aes_key, "pc": None}

        response_data = {
            "access_token": new_access_token,
            "user_id": user_id,
            "username": username,
            "name": user_data.get("name", ""),
            "profile_pic": user_data.get("profile_pic", "")
        }
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="refresh_token",
            success=True,
            payload=response_data
        )
        logging.info(
            f"{user_id} access token refreshed successfully.")
    except Exception as e:
        logging.error("Failed to refresh access token: " + str(e))
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type="refresh_token",
            success=False,
            error_code="REFRESH_FAILED",
            error_message=str(e)
        )
