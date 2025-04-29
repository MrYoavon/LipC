# handlers/auth_handler.py
import logging
import re
import bcrypt

from database.users import create_user, get_user_by_id, get_user_by_username
from services.jwt_utils import (
    create_access_token, create_refresh_token,
    refresh_access_token, verify_jwt
)
from services.state import clients
from services.crypto_utils import structure_encrypt_send_message, send_error_message
from constants import NAME_PART_MAX_LENGTH, USERNAME_MAX_LENGTH, PASSWORD_MAX_LENGTH

# -----------------------------------------------------------------------------
# Authentication Handlers
# -----------------------------------------------------------------------------


async def handle_authentication(websocket, data, aes_key):
    """
    Authenticate user credentials and return access & refresh tokens.
    """
    msg_type = "authenticate"
    payload = data.get("payload", {})
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="AUTH_MISSING_CREDENTIALS",
            error_message="Username and password are required.",
        )
        return

    # Length validation
    if len(username) > USERNAME_MAX_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="CREDENTIALS_TOO_LONG",
            error_message=f"Username must be at most {USERNAME_MAX_LENGTH} chars and password at most {PASSWORD_MAX_LENGTH} chars.",
        )
        return

    user = get_user_by_username(username)
    if not user:
        logging.info(f"Authentication failed: user '{username}' not found.")
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="USER_NOT_FOUND",
            error_message="User does not exist.",
        )
        return

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        logging.info(
            f"Authentication failed: incorrect password for '{username}'.")
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="INCORRECT_PASSWORD",
            error_message="Incorrect password.",
        )
        return

    user_id = str(user["_id"])
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    # Register client session
    clients[user_id] = {"ws": websocket,
                        "username": username, "aes_key": aes_key, "pc": None}
    logging.info(f"User '{username}' authenticated with ID {user_id}.")

    response = {
        "user_id": user_id,
        "name": user.get("name", ""),
        "profile_pic": user.get("profile_pic", ""),
        "access_token": access_token,
        "refresh_token": refresh_token
    }
    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type=msg_type,
        success=True,
        payload=response
    )


async def handle_signup(websocket, data, aes_key):
    """
    Register a new user and issue JWT tokens.
    """
    msg_type = "signup"
    payload = data.get("payload", {})
    username = payload.get("username")
    password = payload.get("password")
    name = payload.get("name", "")

    # Basic field check
    if not username or not password or not name:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="SIGNUP_MISSING_CREDENTIALS",
            error_message="Username, name and password are required.",
        )
        return

    # Length validation
    if len(username) > USERNAME_MAX_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="FIELDS_TOO_LONG",
            error_message=f"Username must be <= {USERNAME_MAX_LENGTH} chars and password <= {PASSWORD_MAX_LENGTH} chars.",
        )
        return

    # Validate name: exactly two parts, English letters, each <= NAME_PART_MAX_LEN
    name_parts = name.strip().split()
    if (
        len(name_parts) != 2
        or any(not re.match(r'^[A-Za-z]+$', part) for part in name_parts)
        or any(len(part) > NAME_PART_MAX_LENGTH for part in name_parts)
    ):
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="INVALID_NAME_FORMAT",
            error_message=f"Name must be "
            "two English names, each <= {NAME_PART_MAX_LEN} chars.",
        )
        return

    # Validate username: alphanumeric and underscores only
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="INVALID_USERNAME",
            error_message="Username can only contain letters, numbers, and underscores.",
        )
        return

    # Password complexity: min 8 chars, uppercase, lowercase, digit, special
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*\W).{8,}$'
    if not re.match(pattern, password):
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="WEAK_PASSWORD",
            error_message="Password must be at least 8 characters long and include uppercase, lowercase, number, and special character.",
        )
        return

    # Username uniqueness
    if get_user_by_username(username):
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="USERNAME_EXISTS",
            error_message="Username already exists.",
        )
        return

    # Hash password
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_data = {
        "username": username,
        "password_hash": hashed,
        "name": name,
        "profile_pic": payload.get("profile_pic", ""),
        "contacts": []
    }
    user_id = str(create_user(user_data))

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    # Register client session
    clients[user_id] = {"ws": websocket,
                        "username": username, "aes_key": aes_key, "pc": None}
    logging.info(f"New user '{username}' registered with ID {user_id}.")

    response = {"user_id": user_id, "access_token": access_token,
                "refresh_token": refresh_token}
    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type=msg_type,
        success=True,
        payload=response
    )


async def handle_token_refresh(websocket, data, aes_key):
    """
    Refresh the access token using a valid refresh token.
    """
    msg_type = "refresh_token"
    payload = data.get("payload", {})
    refresh_jwt = payload.get("refresh_jwt")

    if not refresh_jwt:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="MISSING_REFRESH_TOKEN",
            error_message="Refresh token is required.",
        )
        return

    try:
        # Validate and refresh token
        token_data = verify_jwt(refresh_jwt, expected_type="refresh")
        user_id = token_data.get("sub")
        new_access = refresh_access_token(refresh_jwt)
        user = get_user_by_id(user_id)
        username = user.get("username", "")

        # Update client session
        clients[user_id] = {"ws": websocket,
                            "username": username, "aes_key": aes_key, "pc": None}
        response = {
            "user_id": user_id,
            "username": username,
            "name": user.get("name", ""),
            "profile_pic": user.get("profile_pic", ""),
            "access_token": new_access
        }
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            success=True,
            payload=response
        )
        logging.info(f"Access token refreshed for user ID {user_id}.")
    except Exception as e:
        logging.error(f"Failed to refresh token: {e}")
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="REFRESH_FAILED",
            error_message=str(e),
        )


async def handle_logout(websocket, data, aes_key):
    """
    Handle user logout by removing the session.
    """
    msg_type = "logout"
    payload = data.get("payload", {})
    user_id = payload.get("user_id")

    if not user_id:
        await send_error_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            error_code="MISSING_USER_ID",
            error_message="User ID is required.",
        )
        return

    # Remove client session
    clients.pop(user_id, None)
    logging.info(f"User ID {user_id} logged out.")
    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type=msg_type,
        success=True,
        payload={"message": "Logged out successfully."}
    )
