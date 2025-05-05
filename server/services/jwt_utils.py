# services/jwt_utils.py
import hashlib
import os
import datetime
import uuid
import jwt
import logging
from dotenv import load_dotenv

from database.refresh_tokens import find_valid_token, revoke_previous_token, revoke_token, save_refresh_token

load_dotenv()
logger = logging.getLogger(__name__)

# --- RSA Key Configuration ---
# Your RSA private key and public key should be stored securely.
# For instance, they can be provided via environment variables.
# The private key is used to sign tokens (RS256), and the public key is used to verify them.
RSA_PRIVATE_KEY = os.getenv("JWT_RSA_PRIVATE_KEY")
RSA_PUBLIC_KEY = os.getenv("JWT_RSA_PUBLIC_KEY")

if not RSA_PRIVATE_KEY or not RSA_PUBLIC_KEY:
    logger.error(
        "RSA keys not set; please configure JWT_RSA_PRIVATE_KEY and JWT_RSA_PUBLIC_KEY in the environment.")

# Use RS256 signing algorithm.
JWT_ALGORITHM = "RS256"

# Expiration configuration
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(user_id: str, additional_claims: dict = None) -> str:
    """
    Generate a signed JWT access token.

    Args:
        user_id (str): Subject identifier (user ID).
        additional_claims (dict, optional): Extra claims to include in the token.

    Returns:
        str: Encoded JWT string signed with the RSA private key.

    Raises:
        jwt.PyJWTError: If token encoding fails.
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


async def create_refresh_token(user_id: str, additional_claims: dict = None) -> str:
    """
    Generate a signed JWT refresh token and persist its hash.

    Args:
        user_id (str): Subject identifier (user ID).
        additional_claims (dict, optional): Extra claims to include.

    Returns:
        str: Encoded refresh JWT.

    Raises:
        jwt.PyJWTError: If token encoding fails.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid.uuid4())  # Unique identifier for the token

    # Revoke the previous token (if any) and tag it
    await revoke_previous_token(user_id, replaced_by_jti=jti)

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": exp,
        "jti": jti,
        "type": "refresh"
    }
    if additional_claims:
        payload.update(additional_claims)
    token = jwt.encode(payload, RSA_PRIVATE_KEY, algorithm=JWT_ALGORITHM)

    await save_refresh_token(
        user_id=user_id,
        jti=jti,
        token_hash=_hash(token),
        expires_at=exp
    )
    return token


def verify_jwt(token: str, expected_type: str = "access") -> dict:
    """
    Decode and validate a JWT signature and claims.

    Args:
        token (str): JWT string to verify.
        expected_type (str): Expected 'type' claim value ('access' or 'refresh').

    Returns:
        dict: Decoded JWT payload.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If signature invalid or type mismatch.
    """
    try:
        # The public key is used to verify the signature.
        payload = jwt.decode(token, RSA_PUBLIC_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != expected_type:
            raise jwt.InvalidTokenError(
                f"Token type mismatch. Expected '{expected_type}' token.")
        return payload
    except jwt.ExpiredSignatureError as e:
        logger.error("JWT expired: " + str(e))
        raise
    except jwt.InvalidTokenError as e:
        logger.error("Invalid JWT token: " + str(e))
        raise


def verify_jwt_in_message(token: str, expected_type: str, user_id: str) -> dict:
    """
    Validate a JWT within a message context and match its subject.

    Args:
        token (str): JWT string from client message.
        expected_type (str): Expected token type.
        user_id (str): Declared user ID to match the token 'sub'.

    Returns:
        tuple:
            bool: True if valid, False otherwise.
            dict: Payload on success, or error info on failure.
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
        logger.error("Access token expired: " + str(e))
        return False, {
            "error": "TOKEN_EXPIRED",
            "message": "Your access token has expired. Please refresh your token or log in again."
        }
    except jwt.InvalidTokenError as e:
        logger.error("Invalid access token: " + str(e))
        return False, {
            "error": "INVALID_TOKEN",
            "message": "Your access token is invalid. Please log in again."
        }


async def refresh_access_token(refresh_token: str) -> str:
    """
    Issue a new access token if the provided refresh token is valid.

    Args:
        refresh_token (str): Existing refresh JWT.

    Returns:
        str: New access token JWT.

    Raises:
        jwt.ExpiredSignatureError: If the refresh token is expired.
        jwt.InvalidTokenError: If the token is invalid or revoked.
    """
    try:
        payload = verify_jwt(refresh_token, expected_type="refresh")
        jti = payload["jti"]
        token_hash = _hash(refresh_token)

        # 1) Must exist in DB, not revoked, not past its DB expiry timestamp
        if not await find_valid_token(jti, token_hash):
            raise jwt.InvalidTokenError("Refresh token revoked or unknown.")

        # 2) Still good – issue a new access token
        user_id = payload["sub"]
        return create_access_token(user_id)

    except jwt.ExpiredSignatureError:
        # Token passed its exp: revoke record & bubble error so caller logs user out
        try:
            decoded = jwt.decode(
                refresh_token,
                RSA_PUBLIC_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"verify_exp": False}  # ignore exp for decoding only
            )
            await revoke_token(decoded["jti"], reason="expired")
        except Exception:
            pass  # token may be corrupt – ignore
        raise

    except jwt.InvalidTokenError as exc:
        # Further hardening: revoke on bad signature or tamper detection
        try:
            decoded = jwt.decode(
                refresh_token,
                RSA_PUBLIC_KEY,
                algorithms=[JWT_ALGORITHM],
                options={"verify_signature": False, "verify_exp": False}
            )
            await revoke_token(decoded.get("jti", "unknown"), reason="invalid")
        except Exception:
            pass
        raise


def _hash(token: str) -> str:
    """
    Compute SHA-256 hash of a token string.

    Args:
        token (str): Token to hash.

    Returns:
        str: Hexadecimal digest of SHA-256 hash.
    """
    return hashlib.sha256(token.encode()).hexdigest()
