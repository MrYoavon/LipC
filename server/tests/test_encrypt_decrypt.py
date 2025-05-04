import pytest
import asyncio
from services.crypto_utils import encrypt_message, decrypt_message


def test_encrypt_decrypt_roundtrip():
    key = b"\x00" * 32
    plaintext = b"hello world"
    enc = encrypt_message(key, plaintext)
    dec = decrypt_message(key, enc["nonce"], enc["ciphertext"], enc["tag"])
    assert dec == plaintext
