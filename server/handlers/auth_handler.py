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

logger = logging.getLogger(__name__)


class AuthHandler:
    """
    Handles user authentication workflows: login, signup, token refresh, logout.
    """

    async def handle_authentication(self, websocket, data, aes_key):
        """
        Authenticate user credentials and send access & refresh tokens.

        Performs validation on provided username and password, checks against stored
        credentials, and upon success issues JWT access and refresh tokens. Registers
        the client session in memory.

        Args:
            websocket: WebSocket connection instance used for communication.
            data (dict): Parsed message data, expected to contain 'payload' with 'username' and 'password'.
            aes_key (bytes): AES key used to encrypt responses.

        Returns:
            None

        Side Effects:
            Sends an encrypted success or error message over the websocket.
        """
        msg_type = "authenticate"
        payload = data.get("payload", {})
        username = payload.get("username")
        password = payload.get("password")

        if not username or not password:
            return await send_error_message(websocket, aes_key, msg_type,
                                            "AUTH_MISSING_CREDENTIALS", "Username and password are required.")

        # Length validation
        if len(username) > USERNAME_MAX_LENGTH or len(password) > PASSWORD_MAX_LENGTH:
            return await send_error_message(websocket, aes_key, msg_type,
                                            "CREDENTIALS_TOO_LONG",
                                            f"Username ≤{USERNAME_MAX_LENGTH}, password ≤{PASSWORD_MAX_LENGTH} chars.")

        user = get_user_by_username(username)
        if not user:
            logger.info(f"Authentication failed: user '{username}' not found.")
            await send_error_message(
                websocket=websocket,
                aes_key=aes_key,
                msg_type=msg_type,
                error_code="USER_NOT_FOUND",
                error_message="User does not exist.",
            )
            return

        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            logger.info(
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
        logger.info(f"User '{username}' authenticated with ID {user_id}.")

        response = {
            "user_id": user_id,
            "name": user.get("name", ""),
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

    async def handle_signup(self, websocket, data, aes_key):
        """
        Register a new user, hash their password, and issue JWT tokens.

        Validates the provided signup payload (username, password, name), ensures
        uniqueness and format requirements, creates the user in the database,
        and returns access & refresh tokens.

        Args:
            websocket: WebSocket connection instance used for communication.
            data (dict): Parsed message data, expected to contain 'payload' with 'username', 'password', and 'name'.
            aes_key (bytes): AES key used to encrypt responses.

        Returns:
            None

        Side Effects:
            Sends an encrypted success or error message over the websocket.
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
            "contacts": []
        }
        user_id = str(create_user(user_data))

        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        # Register client session
        clients[user_id] = {"ws": websocket,
                            "username": username, "aes_key": aes_key, "pc": None}
        logger.info(f"New user '{username}' registered with ID {user_id}.")

        response = {"user_id": user_id, "access_token": access_token,
                    "refresh_token": refresh_token}
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            success=True,
            payload=response
        )

    async def handle_refresh_token(self, websocket, data, aes_key):
        """
        Refresh the access token using a valid refresh JWT.

        Validates the provided refresh token, issues a new access token,
        and updates the client session.

        Args:
            websocket: WebSocket connection instance used for communication.
            data (dict): Parsed message data, expected to contain 'payload' with 'refresh_jwt'.
            aes_key (bytes): AES key used to encrypt responses.

        Returns:
            None

        Side Effects:
            Sends an encrypted success or error message over the websocket.
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
                "access_token": new_access
            }
            await structure_encrypt_send_message(
                websocket=websocket,
                aes_key=aes_key,
                msg_type=msg_type,
                success=True,
                payload=response
            )
            logger.info(f"Access token refreshed for user ID {user_id}.")
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            await send_error_message(
                websocket=websocket,
                aes_key=aes_key,
                msg_type=msg_type,
                error_code="REFRESH_FAILED",
                error_message=str(e),
            )

    async def handle_logout(self, websocket, data, aes_key):
        """
        Handle user logout and remove their session state.

        Expects the 'user_id' field in payload to identify which session to remove.

        Args:
            websocket: WebSocket connection instance used for communication.
            data (dict): Parsed message data, expected to contain 'payload' with 'user_id'.
            aes_key (bytes): AES key used to encrypt responses.

        Returns:
            None

        Side Effects:
            Sends an encrypted success or error message and removes session.
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
        logger.info(f"User ID {user_id} logged out.")
        await structure_encrypt_send_message(
            websocket=websocket,
            aes_key=aes_key,
            msg_type=msg_type,
            success=True,
            payload={"message": "Logged out successfully."}
        )
