// server_connection_indicator.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lip_c/models/server_connection_status.dart';

import '../providers/server_connection_status_provider.dart';
import '../providers/server_helper_provider.dart';

class ServerConnectionIndicator extends ConsumerStatefulWidget {
  final Widget child;
  const ServerConnectionIndicator({super.key, required this.child});

  @override
  _ServerConnectionIndicatorState createState() =>
      _ServerConnectionIndicatorState();
}

class _ServerConnectionIndicatorState
    extends ConsumerState<ServerConnectionIndicator> {
  ServerConnectionStatus? _previousStatus;

  @override
  Widget build(BuildContext context) {
    final connectionStatusAsync = ref.watch(serverConnectionStatusProvider);

    // When data is available, check if the status has changed.
    connectionStatusAsync.whenData((status) {
      if (_previousStatus == null) {
        _previousStatus = status;
        return; // Skip the first build.
      }

      if (_previousStatus != status) {
        _previousStatus = status;
        // Schedule side effects after the build is complete.
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (status == ServerConnectionStatus.connected) {
            ScaffoldMessenger.of(context)
              ..hideCurrentSnackBar()
              ..showSnackBar(
                const SnackBar(
                  content: Text('Connected to server'),
                  backgroundColor: Colors.green,
                  padding: EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                  behavior: SnackBarBehavior.floating,
                  duration: Duration(seconds: 2),
                ),
              );
          } else if (status == ServerConnectionStatus.reconnecting) {
            final serverHelper = ref.read(serverHelperProvider);
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: ValueListenableBuilder<int>(
                  valueListenable: serverHelper.reconnectCountdown,
                  builder: (context, countdown, child) {
                    return Text(
                        'Lost connection. Reconnecting in $countdown seconds...');
                  },
                ),
                backgroundColor: Colors.orange,
                padding: EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                behavior: SnackBarBehavior.floating,
                // Use a long duration to simulate persistence.
                duration: const Duration(days: 1),
              ),
            );
          } else if (status == ServerConnectionStatus.disconnected) {
            ScaffoldMessenger.of(context)
              ..hideCurrentSnackBar()
              ..showSnackBar(
                const SnackBar(
                  content: Text('Disconnected from server'),
                  backgroundColor: Colors.red,
                  duration: Duration(seconds: 2),
                ),
              );
          }
        });
      }
    });

    // Simply return the child widget as the main content.
    return widget.child;
  }
}
