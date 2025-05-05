// lib/providers/server_helper_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../constants.dart';
import '../helpers/crypto_service.dart';
import '../helpers/server_helper.dart';
import '../helpers/app_logger.dart';

/// Provides a single instance of ServerHelper that can be accessed throughout the app.
final serverHelperProvider = Provider<ServerHelper>((ref) {
  final Logger _log = AppLogger.instance;
  _log.i('🔗 Initializing ServerHelper provider');

  final serverHelper = ServerHelper(
    serverUrl: serverUrl,
    cryptoService: CryptoService(),
  );

  // Clean up when the provider is disposed.
  ref.onDispose(() {
    _log.i('✖️ Disposing ServerHelper provider and closing connection');
    serverHelper.closeConnection();
  });

  return serverHelper;
});
