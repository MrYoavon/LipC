import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:jwt_decoder/jwt_decoder.dart';

class JWTTokenService {
  final FlutterSecureStorage _storage = FlutterSecureStorage();
  final String _accessTokenKey = 'access_token';
  final String _refreshTokenKey = 'refresh_token';

  Future<void> saveTokens(String accessToken, String refreshToken) async {
    await _storage.write(key: _accessTokenKey, value: accessToken);
    await _storage.write(key: _refreshTokenKey, value: refreshToken);
  }

  Future<String?> getAccessToken() async {
    return await _storage.read(key: _accessTokenKey);
  }

  Future<String?> getRefreshToken() async {
    return await _storage.read(key: _refreshTokenKey);
  }

  Future<void> clearTokens() async {
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _refreshTokenKey);
  }

  bool isTokenExpired(String token,
      {Duration buffer = const Duration(minutes: 1)}) {
    // Returns true if token is expired or will expire within the buffer duration.
    DateTime expirationDate = JwtDecoder.getExpirationDate(token);
    return expirationDate.subtract(buffer).isBefore(DateTime.now());
  }
}
