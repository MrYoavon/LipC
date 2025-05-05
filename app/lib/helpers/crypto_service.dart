// helpers/crypto_service.dart

import 'dart:convert';
import 'package:cryptography/cryptography.dart';
import 'package:logger/logger.dart';

import 'package:lip_c/helpers/app_logger.dart';

class CryptoService {
  final Logger _log = AppLogger.instance;

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
    _log.i('🔑 Generating ephemeral key pair');
    _keyPair = await keyExchangeAlgorithm.newKeyPair();
    _publicKey = await _keyPair!.extractPublicKey();
    _log.i('🔑 Ephemeral key pair generated');
  }

  /// Returns the client's public key as a Base64-encoded string.
  /// Throws an exception if the key pair has not been generated.
  String getPublicKey() {
    if (_publicKey == null) {
      _log.e('⚠️ getPublicKey called before key pair generation');
      throw Exception("Key pair not generated. Call generateKeyPair() first.");
    }
    final key = base64Encode(_publicKey!.bytes);
    _log.d('📤 Public key: $key');
    return key;
  }

  /// Computes the shared secret using the server's Base64-encoded public key and derives an AES-256 key via HKDF.
  ///
  /// Parameters:
  /// - [serverPublicKeyBase64]: The server's public key as a Base64-encoded string.
  /// - [salt]: A list of bytes used as the salt for key derivation.
  ///
  /// The `info` parameter ("handshake data") provides context for the key derivation and can be adjusted if needed.
  Future<void> computeSharedSecret(String serverPublicKeyBase64, List<int> salt) async {
    _log.i('🔐 Computing shared secret');
    // Decode the server's public key from its Base64 representation.
    final serverBytes = base64Decode(serverPublicKeyBase64);
    final serverPublicKey = SimplePublicKey(
      serverBytes,
      type: KeyPairType.x25519, // Using Curve25519
    );

    // Compute the shared secret using the client's private key and the server's public key.
    _sharedSecret = await keyExchangeAlgorithm.sharedSecretKey(
      keyPair: _keyPair!,
      remotePublicKey: serverPublicKey,
    );
    _log.i('🔐 Shared secret computed');

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
    _log.i('🔐 AES key derived via HKDF');
  }

  /// Encrypts the given [plaintext] using AES-GCM with the derived AES key.
  ///
  /// Returns a map containing the Base64-encoded nonce, ciphertext, and authentication tag.
  Future<Map<String, String>> encryptMessage(String plaintext) async {
    if (_aesKey == null) {
      _log.e('⚠️ encryptMessage called before AES key derivation');
      throw Exception("AES key not derived. Ensure key exchange is complete.");
    }
    _log.d('🔒 Encrypting message: $plaintext');
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
    final result = {
      'nonce': base64Encode(secretBox.nonce),
      'ciphertext': base64Encode(secretBox.cipherText),
      'tag': base64Encode(secretBox.mac.bytes),
    };
    return result;
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
      _log.e('⚠️ decryptMessage called before AES key derivation');
      throw Exception("AES key not derived. Ensure key exchange is complete.");
    }
    _log.d('🔓 Decrypting payload: $encryptedData');
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
    final plaintext = utf8.decode(clearText);
    _log.d('🔓 Decrypted plaintext: $plaintext');
    return plaintext;
  }
}
