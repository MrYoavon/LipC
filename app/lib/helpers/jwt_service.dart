// lib/helpers/jwt_service.dart

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:jwt_decoder/jwt_decoder.dart';
import 'package:logger/logger.dart';
import 'app_logger.dart';

class JWTTokenService {
  final Logger _log = AppLogger.instance;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  final String _accessTokenKey = 'access_token';
  final String _refreshTokenKey = 'refresh_token';

  /// Saves the access and refresh tokens securely.
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    _log.i('🔒 Saving access & refresh tokens');
    await _storage.write(key: _accessTokenKey, value: accessToken);
    await _storage.write(key: _refreshTokenKey, value: refreshToken);
    _log.d('🔒 Tokens saved successfully');
  }

  /// Retrieves the stored access token.
  Future<String?> getAccessToken() async {
    final token = await _storage.read(key: _accessTokenKey);
    _log.d('🔑 Retrieved access token: ${token != null ? 'FOUND' : 'NONE'}');
    return token;
  }

  /// Retrieves the stored refresh token.
  Future<String?> getRefreshToken() async {
    final token = await _storage.read(key: _refreshTokenKey);
    _log.d('🔑 Retrieved refresh token: ${token != null ? 'FOUND' : 'NONE'}');
    return token;
  }

  /// Clears both access and refresh tokens from secure storage.
  Future<void> clearTokens() async {
    _log.i('🗑️ Clearing tokens from storage');
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _refreshTokenKey);
    _log.d('🗑️ Tokens cleared');
  }

  /// Checks if the given JWT is expired or will expire within the buffer duration.
  bool isTokenExpired(
    String token, {
    Duration buffer = const Duration(minutes: 1),
  }) {
    try {
      final expirationDate = JwtDecoder.getExpirationDate(token);
      final willExpireSoon = expirationDate.subtract(buffer).isBefore(DateTime.now());
      _log.d('⏳ Token expiration check: expires at $expirationDate, willExpireSoon=$willExpireSoon');
      return willExpireSoon;
    } catch (e) {
      _log.e('❌ Error checking token expiration', error: e);
      return true;
    }
  }
}
