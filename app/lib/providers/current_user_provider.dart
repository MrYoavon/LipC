import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/lip_c_user.dart';

/// The CurrentUserNotifier manages the state of the connected user.
class CurrentUserNotifier extends StateNotifier<LipCUser?> {
  CurrentUserNotifier() : super(null);

  /// Set the current user.
  void setUser(LipCUser user) {
    state = user;
  }

  /// Clear the current user (log out).
  void clearUser() {
    state = null;
  }
}

/// A StateNotifierProvider to access the current user throughout the app.
final currentUserProvider =
    StateNotifierProvider<CurrentUserNotifier, LipCUser?>((ref) {
  return CurrentUserNotifier();
});
