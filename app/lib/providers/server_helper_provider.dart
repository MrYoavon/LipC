// lib/providers/server_helper_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants.dart';
import '../helpers/server_helper.dart';

/// Provides a single instance of ServerHelper that can be accessed throughout the app.
final serverHelperProvider = Provider<ServerHelper>((ref) {
  final serverHelper = ServerHelper(serverUrl: serverUrl);

  // Register a dispose callback to clean up the connection when the provider is disposed.
  ref.onDispose(() {
    serverHelper.closeConnection();
  });

  return serverHelper;
});
