// lib/providers/current_user_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../models/lip_c_user.dart';

/// The CurrentUserNotifier manages the state of the connected user.
class CurrentUserNotifier extends StateNotifier<LipCUser?> {
  final Logger _log = AppLogger.instance;

  CurrentUserNotifier() : super(null) {
    _log.i('👤 CurrentUserNotifier initialized with no user');
  }

  /// Set the current user.
  void setUser(LipCUser user) {
    _log.i('👤 Setting current user: ${user.username} (ID: ${user.userId})');
    state = user;
  }

  /// Clear the current user (log out).
  void clearUser() {
    if (state != null) {
      _log.i('👤 Clearing current user: ${state!.username}');
    } else {
      _log.w('👤 clearUser called but no user was set');
    }
    state = null;
  }
}

/// A StateNotifierProvider to access the current user throughout the app.
final currentUserProvider = StateNotifierProvider<CurrentUserNotifier, LipCUser?>((ref) {
  return CurrentUserNotifier();
});
