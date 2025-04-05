// providers/server_connection_status_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/server_connection_status.dart';
import 'server_helper_provider.dart';

final serverConnectionStatusProvider =
    StreamProvider<ServerConnectionStatus>((ref) {
  final serverHelper = ref.watch(serverHelperProvider);
  return serverHelper.connectionStatus;
});
