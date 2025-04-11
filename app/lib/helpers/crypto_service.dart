// helpers/crypto_service.dart

import 'dart:convert';
import 'package:cryptography/cryptography.dart';

class CryptoService {
  // -------------------------------------------------------------
  // Key Exchange Algorithm
  // -------------------------------------------------------------
  /// The key exchange algorithm instance. We use X25519 (Curve25519)
  /// because it is efficient and secure for key exchange.
  final X25519 keyExchangeAlgorithm = X25519();

  // -------------------------------------------------------------
  // Ephemeral Key Pair
  // -------------------------------------------------------------
  /// The ephemeral key pair generated for the client during the key exchange.
  SimpleKeyPair? _keyPair;

  /// The public key extracted from the generated ephemeral key pair.
  SimplePublicKey? _publicKey;

  // -------------------------------------------------------------
  // Shared Secret and Derived Keys
  // -------------------------------------------------------------
  /// The shared secret computed using the key exchange with the server's public key.
  SecretKey? _sharedSecret;

  /// The AES key derived from the shared secret using HKDF. This key is used for AES-GCM encryption/decryption.
  SecretKey? _aesKey;

  /// Generates an ephemeral key pair for the client.
  /// This method initializes the client's key pair and extracts its public key.
  Future<void> generateKeyPair() async {
    _keyPair = await keyExchangeAlgorithm.newKeyPair();
    _publicKey = await _keyPair!.extractPublicKey();
  }

  /// Returns the client's public key as a Base64-encoded string.
  /// Throws an exception if the key pair has not been generated.
  String getPublicKey() {
    if (_publicKey == null) {
      throw Exception("Key pair not generated. Call generateKeyPair() first.");
    }
    return base64Encode(_publicKey!.bytes);
  }

  /// Computes the shared secret using the server's Base64-encoded public key and derives an AES-256 key via HKDF.
  ///
  /// Parameters:
  /// - [serverPublicKeyBase64]: The server's public key as a Base64-encoded string.
  /// - [salt]: A list of bytes used as the salt for key derivation.
  ///
  /// The `info` parameter ("handshake data") provides context for the key derivation and can be adjusted if needed.
  Future<void> computeSharedSecret(
      String serverPublicKeyBase64, List<int> salt) async {
    // Decode the server's public key from its Base64 representation.
    final serverPublicKeyBytes = base64Decode(serverPublicKeyBase64);
    final serverPublicKey = SimplePublicKey(
      serverPublicKeyBytes,
      type: KeyPairType.x25519, // Using Curve25519
    );

    // Compute the shared secret using the client's private key and the server's public key.
    _sharedSecret = await keyExchangeAlgorithm.sharedSecretKey(
      keyPair: _keyPair!,
      remotePublicKey: serverPublicKey,
    );

    // Set up the HKDF instance to derive a 256-bit (32 bytes) AES key from the shared secret.
    final hkdf = Hkdf(
      hmac: Hmac(Sha256()),
      outputLength: 32, // 32 bytes = 256 bits
    );

    // Derive the AES key using the shared secret, provided salt (as nonce) and info.
    _aesKey = await hkdf.deriveKey(
      secretKey: _sharedSecret!,
      nonce: salt,
      info: utf8.encode('handshake data'),
    );
  }

  /// Encrypts the given [plaintext] using AES-GCM with the derived AES key.
  ///
  /// Returns a map containing the Base64-encoded nonce, ciphertext, and authentication tag.
  Future<Map<String, String>> encryptMessage(String plaintext) async {
    if (_aesKey == null) {
      throw Exception("AES key not derived. Ensure key exchange is complete.");
    }
    // Create an AES-GCM algorithm instance with 256-bit key support.
    final algorithm = AesGcm.with256bits();
    // Generate a new nonce for the encryption operation.
    final nonce = algorithm.newNonce();
    // Encrypt the plaintext (after encoding it as UTF-8) with the derived AES key and generated nonce.
    final secretBox = await algorithm.encrypt(
      utf8.encode(plaintext),
      secretKey: _aesKey!,
      nonce: nonce,
    );
    // Return the encryption results with nonce, ciphertext, and MAC encoded in Base64.
    return {
      'nonce': base64Encode(secretBox.nonce),
      'ciphertext': base64Encode(secretBox.cipherText),
      'tag': base64Encode(secretBox.mac.bytes),
    };
  }

  /// Decrypts an encrypted message.
  ///
  /// The [encryptedData] map must contain Base64-encoded values for:
  /// - 'nonce'
  /// - 'ciphertext'
  /// - 'tag'
  ///
  /// Returns the decrypted plaintext as a String.
  Future<String> decryptMessage(Map<String, dynamic> encryptedData) async {
    if (_aesKey == null) {
      throw Exception("AES key not derived. Ensure key exchange is complete.");
    }
    // Create an AES-GCM algorithm instance with 256-bit key support.
    final algorithm = AesGcm.with256bits();
    // Create a SecretBox containing the ciphertext, nonce, and MAC after decoding them from Base64.
    final secretBox = SecretBox(
      base64Decode(encryptedData['ciphertext'] as String),
      nonce: base64Decode(encryptedData['nonce'] as String),
      mac: Mac(base64Decode(encryptedData['tag'] as String)),
    );
    // Decrypt the ciphertext using the derived AES key.
    final clearText = await algorithm.decrypt(
      secretBox,
      secretKey: _aesKey!,
    );
    // Decode the decrypted bytes into a UTF-8 String.
    return utf8.decode(clearText);
  }
}
