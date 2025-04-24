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
    jti = str(uuid.uuid4())  # Unique identifier for the token

    # Revoke the previous token (if any) and tag it
    revoke_previous_token(user_id, replaced_by_jti=jti)

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

    save_refresh_token(
        user_id=user_id,
        jti=jti,
        token_hash=_hash(token),
        expires_at=exp
    )
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
    Validate the *existing* refresh token and, if valid,
    return a new short-lived access token.  The same refresh
    token remains usable until it naturally expires.
    """
    try:
        payload = verify_jwt(refresh_token, expected_type="refresh")
        jti = payload["jti"]
        token_hash = _hash(refresh_token)

        # 1) Must exist in DB, not revoked, not past its DB expiry timestamp
        if not find_valid_token(jti, token_hash):
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
            revoke_token(decoded["jti"], reason="expired")
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
            revoke_token(decoded.get("jti", "unknown"), reason="invalid")
        except Exception:
            pass
        raise


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
