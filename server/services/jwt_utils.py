# services/jwt_utils.py
import os
import datetime
import jwt
import logging
from dotenv import load_dotenv

load_dotenv()

# --- RSA Key Configuration ---
# Your RSA private key and public key should be stored securely.
# For instance, they can be provided via environment variables.
# The private key is used to sign tokens (RS256), and the public key is used to verify them.
RSA_PRIVATE_KEY = os.getenv("JWT_RSA_PRIVATE_KEY")
RSA_PUBLIC_KEY = os.getenv("JWT_RSA_PUBLIC_KEY")

if not RSA_PRIVATE_KEY or not RSA_PUBLIC_KEY:
    logging.error(
        "RSA keys not set; please configure JWT_RSA_PRIVATE_KEY and JWT_RSA_PUBLIC_KEY in the environment.")

# Use RS256 signing algorithm.
JWT_ALGORITHM = "RS256"

# Expiration configuration
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(user_id: str, additional_claims: dict = None) -> str:
    """
    Create a short-lived access token using RS256 for signing.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": exp,
        "type": "access"
    }
    if additional_claims:
        payload.update(additional_claims)
    token = jwt.encode(payload, RSA_PRIVATE_KEY, algorithm=JWT_ALGORITHM)
    return token


def create_refresh_token(user_id: str, additional_claims: dict = None) -> str:
    """
    Create a longer-lived refresh token, also signed with RS256.
    The "type" claim distinguishes it from an access token.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": exp,
        "type": "refresh"
    }
    if additional_claims:
        payload.update(additional_claims)
    token = jwt.encode(payload, RSA_PRIVATE_KEY, algorithm=JWT_ALGORITHM)
    return token


def verify_jwt(token: str, expected_type: str = "access") -> dict:
    """
    Decode and validate a JWT using RS256.
    This function verifies that the token hasn't expired and that its "type" matches the expected type.
    """
    try:
        # The public key is used to verify the signature.
        payload = jwt.decode(token, RSA_PUBLIC_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != expected_type:
            raise jwt.InvalidTokenError(
                f"Token type mismatch. Expected '{expected_type}' token.")
        return payload
    except jwt.ExpiredSignatureError as e:
        logging.error("JWT expired: " + str(e))
        raise
    except jwt.InvalidTokenError as e:
        logging.error("Invalid JWT token: " + str(e))
        raise


def verify_jwt_in_message(token: str, expected_type: str, user_id: str) -> dict:
    """
    Verify a JWT token in the context of a message type.
    This function checks the token's validity and extracts the payload.
    """
    if not token:
        return False, {
            "error": "MISSING_TOKEN",
            "message": "Access token is missing. Please log in again."
        }
    try:
        payload = verify_jwt(token, expected_type=expected_type)
        if payload.get("sub") != user_id:
            return False, {
                "error": "INVALID_USER",
                "message": "The token does not match the user ID."
            }
        return True, payload
    except jwt.ExpiredSignatureError as e:
        logging.error("Access token expired: " + str(e))
        return False, {
            "error": "TOKEN_EXPIRED",
            "message": "Your access token has expired. Please refresh your token or log in again."
        }
    except jwt.InvalidTokenError as e:
        logging.error("Invalid access token: " + str(e))
        return False, {
            "error": "INVALID_TOKEN",
            "message": "Your access token is invalid. Please log in again."
        }


def refresh_access_token(refresh_token: str) -> str:
    """
    Validate a refresh token and generate a new access token.
    The refresh token must be valid, unexpired, and explicitly marked as a refresh token.
    """
    try:
        payload = verify_jwt(refresh_token, expected_type="refresh")
        user_id = payload.get("sub")
        if not user_id:
            raise Exception("Invalid refresh token: missing subject.")
        # Additional checks (for token revocation, etc.) could be added here.
        return create_access_token(user_id)
    except Exception as e:
        logging.error("Failed to refresh access token: " + str(e))
        raise
