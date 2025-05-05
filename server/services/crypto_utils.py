import json
import logging
import os
import base64
import uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


logger = logging.getLogger(__name__)


def generate_ephemeral_key():
    """
    Generate an ephemeral X25519 key pair.

    Returns:
        tuple:
            private_key (X25519PrivateKey): Generated private key.
            public_key (X25519PublicKey): Corresponding public key.
    """
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def serialize_public_key(public_key):
    """
    Serialize a public key to raw bytes.

    Args:
        public_key (X25519PublicKey): The public key to serialize.

    Returns:
        bytes: Raw-format public key bytes.
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )


def deserialize_public_key(public_key_bytes):
    """
    Deserialize raw public key bytes into an X25519PublicKey.

    Args:
        public_key_bytes (bytes): Raw public key bytes.

    Returns:
        X25519PublicKey: Reconstructed public key object.
    """
    return X25519PublicKey.from_public_bytes(public_key_bytes)


def compute_shared_secret(own_private_key, peer_public_key):
    """
    Compute shared secret via X25519 ECDH.

    Args:
        own_private_key (X25519PrivateKey): Local private key.
        peer_public_key (X25519PublicKey): Remote party's public key.

    Returns:
        bytes: Shared secret bytes.

    Raises:
        Exception: If the exchange operation fails.
    """
    try:
        shared_secret = own_private_key.exchange(peer_public_key)
        return shared_secret
    except Exception as e:
        raise Exception("Error computing shared secret: " + str(e))


def derive_aes_key(shared_secret, salt, info=b'handshake data'):
    """
    Derive a 256-bit AES key using HKDF-SHA256.

    Args:
        shared_secret (bytes): ECDH-generated shared secret.
        salt (bytes): Salt value for HKDF.
        info (bytes, optional): Context info. Defaults to b'handshake data'.

    Returns:
        bytes: 32-byte AES key.

    Raises:
        Exception: If key derivation fails.
    """
    try:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # 32 bytes equals 256 bits
            salt=salt,
            info=info,
            backend=default_backend()
        )
        aes_key = hkdf.derive(shared_secret)
        return aes_key
    except Exception as e:
        raise Exception("Error deriving AES key: " + str(e))


def encrypt_message(aes_key, plaintext):
    """
    Encrypt plaintext bytes using AES-GCM.

    Args:
        aes_key (bytes): 32-byte AES key.
        plaintext (bytes): Data to encrypt.

    Returns:
        dict: {
            'nonce': bytes,  # 12-byte nonce
            'ciphertext': bytes,
            'tag': bytes     # 16-byte authentication tag
        }

    Raises:
        Exception: If encryption fails.
    """
    try:
        nonce = os.urandom(12)  # Generate a 96-bit nonce for AES-GCM
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        tag = encryptor.tag
        return {
            'nonce': nonce,
            'ciphertext': ciphertext,
            'tag': tag
        }
    except Exception as e:
        raise Exception("Encryption failed: " + str(e))


def decrypt_message(aes_key, nonce, ciphertext, tag):
    """
    Decrypt AES-GCM encrypted data.

    Args:
        aes_key (bytes): AES key used for decryption.
        nonce (bytes): Nonce used during encryption.
        ciphertext (bytes): Encrypted data.
        tag (bytes): Authentication tag.

    Returns:
        bytes: Decrypted plaintext.

    Raises:
        Exception: If decryption fails or integrity check fails.
    """
    try:
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        return plaintext
    except Exception as e:
        raise Exception("Decryption failed: " + str(e))


async def send_encrypted(websocket, plaintext, aes_key):
    """
    Encrypt and send a JSON payload over a websocket.

    Args:
        websocket: WebSocket connection.
        plaintext (str): JSON-formatted string to encrypt.
        aes_key (bytes): AES key for encryption.

    Raises:
        Logs error on failure.
    """
    try:
        # Convert the plaintext string to bytes.
        data_bytes = plaintext.encode('utf-8')
        # Encrypt the bytes using AES-GCM.
        encrypted = encrypt_message(aes_key, data_bytes)
        # Prepare the JSON payload with base64-encoded encryption parameters.
        payload = {
            'nonce': base64.b64encode(encrypted['nonce']).decode('utf-8'),
            'ciphertext': base64.b64encode(encrypted['ciphertext']).decode('utf-8'),
            'tag': base64.b64encode(encrypted['tag']).decode('utf-8')
        }
        # Send the encrypted payload over the websocket.
        await websocket.send(json.dumps(payload))
    except Exception as e:
        logger.error("Failed to send encrypted message: " + str(e))


async def structure_encrypt_send_message(
    websocket,
    aes_key,
    msg_type,
    success=True,
    payload=None,
    error_code=None,
    error_message=None,
):
    """
    Build and send a structured server response message encrypted over a websocket.

    Args:
        websocket: WebSocket connection.
        aes_key (bytes): AES key.
        msg_type (str): Message type identifier.
        success (bool, optional): Operation status. Defaults to True.
        payload (dict, optional): Response data. Defaults to {}.
        error_code (str, optional): Error code on failure.
        error_message (str, optional): Error description on failure.

    The structured payload contains:
      - message_id: A new unique identifier for each response.
      - timestamp: The UTC timestamp when the message was created.
      - msg_type: The type of message.
      - success: Boolean indicator of operation status.
      - error_code and error_message: Only populated if the request failed.
      - payload: Operation-specific data.

    After constructing the payload, the function converts it to a JSON string and calls the send_encrypted() utility
    to wrap the message with the encryption envelope (nonce, ciphertext, tag) before sending over the websocket.

    Raises:
        Logs error on failure.
    """
    message = {
        "message_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "msg_type": msg_type,
        "success": success,
        "payload": payload if payload is not None else {}
    }
    if not success:
        message["error_code"] = error_code if error_code else "UNKNOWN_ERROR"
        message["error_message"] = error_message if error_message else "An unknown error occurred."

    try:
        # Convert the message dictionary to a JSON string.
        plaintext = json.dumps(message)
        # Encrypt the message and send it over the websocket.
        await send_encrypted(websocket, plaintext, aes_key)
    except Exception as e:
        logger.error("Failed to send structured encrypted message: " + str(e))


async def send_error_message(
    websocket,
    aes_key,
    msg_type,
    error_code,
    error_message,
):
    """
    Send a structured error message over a websocket.

    Args:
        websocket: WebSocket connection.
        aes_key (bytes): AES key for encryption.
        msg_type (str): Original message type.
        error_code (str): Error code identifier.
        error_message (str): Human-readable error message.

    Raises:
        Logs error on failure.
    """
    await structure_encrypt_send_message(
        websocket,
        aes_key,
        msg_type=msg_type,
        success=False,
        payload=None,
        error_code=error_code,
        error_message=error_message
    )
