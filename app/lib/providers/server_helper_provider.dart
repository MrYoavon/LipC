// lib/providers/server_helper_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../constants.dart';
import '../helpers/server_helper.dart';

/// Provides a single instance of ServerHelper that can be accessed throughout the app.
final serverHelperProvider = Provider<ServerHelper>((ref) {
  return ServerHelper(serverUrl: serverUrl);
});
