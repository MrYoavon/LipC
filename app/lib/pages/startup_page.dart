// lib/pages/startup_page.dart

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../models/lip_c_user.dart';
import '../pages/contacts_page.dart';
import '../pages/login_page.dart';
import '../pages/splash_screen.dart';
import '../providers/server_helper_provider.dart';
import '../providers/current_user_provider.dart';
import '../providers/contacts_provider.dart';

/// StartupPage handles the splash screen, attempts auto-login,
/// and navigates to the appropriate page (Contacts or Login).
class StartupPage extends ConsumerStatefulWidget {
  const StartupPage({super.key});

  @override
  ConsumerState<StartupPage> createState() => _StartupPageState();
}

class _StartupPageState extends ConsumerState<StartupPage> {
  final Logger _log = AppLogger.instance;

  @override
  void initState() {
    super.initState();
    _log.i('💡 StartupPage mounted');
    _attemptAutoLogin();
  }

  Future<void> _attemptAutoLogin() async {
    _log.i('🔄 Attempting auto-login');
    final serverHelper = ref.read(serverHelperProvider);

    try {
      final result = await serverHelper.tryAutoLogin();
      _log.d('🛰️ Auto-login response: $result');

      if (result['success'] == true) {
        final user = LipCUser(
          userId: result['user_id'],
          username: result['username'],
          name: result['name'],
          profilePic: result['profile_pic'],
        );
        _log.i('✅ Auto-login succeeded for ${user.username}');

        // Update providers with the logged-in user
        ref.read(currentUserProvider.notifier).setUser(user);
        ref.read(contactsProvider(user.userId).notifier).loadContacts();

        if (!mounted) return;
        _log.i('➡️ Navigating to ContactsPage');
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const ContactsPage()),
        );
      } else {
        _log.w('⚠️ Auto-login failed, redirecting to LoginPage');
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const LoginPage()),
        );
      }
    } catch (e, st) {
      _log.e('❌ Auto-login error', error: e, stackTrace: st);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoginPage()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    // Always show splash while deciding where to go
    return const SplashScreen();
  }

  @override
  void dispose() {
    _log.i('🗑️ StartupPage disposed');
    super.dispose();
  }
}
