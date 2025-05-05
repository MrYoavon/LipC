// lib/providers/server_connection_status_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../models/server_connection_status.dart';
import 'server_helper_provider.dart';

/// Provides a stream of ServerConnectionStatus, logging each update.
final serverConnectionStatusProvider = StreamProvider<ServerConnectionStatus>((ref) {
  final Logger _log = AppLogger.instance;
  _log.i('🔄 Subscribing to serverConnectionStatusProvider');

  final serverHelper = ref.watch(serverHelperProvider);
  return serverHelper.connectionStatus.map((status) {
    _log.d('🌐 Server connection status updated: $status');
    return status;
  });
});
