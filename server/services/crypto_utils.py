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


def generate_ephemeral_key():
    """
    Generate an ephemeral key pair using the X25519 algorithm.
    This function creates a private key and derives the corresponding public key.
    """
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def serialize_public_key(public_key):
    """
    Serialize a public key to its raw bytes format.
    The public key is encoded in raw format (which is not human-readable)
    using base encoding later if needed.
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )


def deserialize_public_key(public_key_bytes):
    """
    Deserialize raw-format public key bytes back into a public key object.
    This is used to reconstruct the public key received from a peer.
    """
    return X25519PublicKey.from_public_bytes(public_key_bytes)


def compute_shared_secret(own_private_key, peer_public_key):
    """
    Compute the shared secret using Elliptic-curve Diffie–Hellman (ECDH).
    Given our private key and the peer's public key, the shared secret
    is generated, enabling secure key derivation.
    """
    try:
        shared_secret = own_private_key.exchange(peer_public_key)
        return shared_secret
    except Exception as e:
        raise Exception("Error computing shared secret: " + str(e))


def derive_aes_key(shared_secret, salt, info=b'handshake data'):
    """
    Derive a 256-bit AES key from the shared secret using the HKDF key derivation function.

    Parameters:
      shared_secret: The ECDH-generated shared secret.
      salt: Salt value (should be provided in bytes)
      info: Contextual information for the HKDF (defaults to b'handshake data').

    Returns:
      The derived AES key (32 bytes for a 256-bit key).
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
    Encrypt a plaintext byte string using AES in Galois/Counter Mode (GCM).

    Parameters:
      aes_key: The AES encryption key.
      plaintext: The plaintext bytes to be encrypted.

    Returns:
      A dictionary containing:
        - 'nonce': A randomly generated nonce (recommended 96 bits for GCM),
        - 'ciphertext': The resulting ciphertext,
        - 'tag': The authentication tag used for verifying integrity.
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
    Decrypt ciphertext encrypted using AES-GCM.

    Parameters:
      aes_key: The AES decryption key.
      nonce: The nonce used during encryption.
      ciphertext: The encrypted ciphertext.
      tag: The authentication tag accompanying the ciphertext.

    Returns:
      The decrypted plaintext bytes.
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
    Encrypt a plaintext string and send it through the given websocket.

    The function:
      1. Encodes the plaintext into bytes.
      2. Encrypts the byte message using AES-GCM.
      3. Encodes the encryption parameters (nonce, ciphertext, tag) in base64.
      4. Sends the resulting JSON payload over the websocket.

    Parameters:
      websocket: The websocket connection to use.
      plaintext: The plain text string to send.
      aes_key: The AES key for encryption.
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
        logging.error("Failed to send encrypted message: " + str(e))


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

    Parameters:
      websocket: The websocket connection object.
      aes_key: The AES key for encryption.
      msg_type (str): A string indicating the type of response.
      success (bool): True if the server process was successful.
      payload (dict, optional): Operation-specific response data; defaults to an empty dict if None.
      error_code (str, optional): An error identifier code, used when success is False.
      error_message (str, optional): A descriptive error message for unsuccessful operations.

    The structured payload contains:
      - message_id: A new unique identifier for each response.
      - timestamp: The UTC timestamp when the message was created.
      - msg_type: The type of message.
      - success: Boolean indicator of operation status.
      - error_code and error_message: Only populated if the request failed.
      - payload: Operation-specific data.

    After constructing the payload, the function converts it to a JSON string and calls the send_encrypted() utility
    to wrap the message with the encryption envelope (nonce, ciphertext, tag) before sending over the websocket.
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
        logging.error("Failed to send structured encrypted message: " + str(e))


async def send_error_message(
    websocket,
    aes_key,
    msg_type,
    error_code,
    error_message,
):
    """
    Send an error message over the websocket connection.

    Parameters:
      websocket: The websocket connection object.
      aes_key: The AES key for encryption.
      msg_type (str): The type of message.
      error_code (str): A string representing the error code.
      error_message (str): A descriptive error message.

    This function constructs a structured error message and sends it using the send_encrypted() utility.
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
