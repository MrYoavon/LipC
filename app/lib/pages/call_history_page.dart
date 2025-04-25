import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../models/call_history_entry.dart';
import '../helpers/call_history_service.dart';
import '../providers/contacts_provider.dart';
import '../widgets/server_connection_indicator.dart';
import 'call_transcript_page.dart';

class CallHistoryPage extends ConsumerWidget {
  final CallHistoryService service;
  final String userId;

  const CallHistoryPage({
    super.key,
    required this.service,
    required this.userId,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final Logger _log = AppLogger.instance;
    _log.i('📜 Requesting call history for user: $userId');
    service.requestCallHistory(userId);

    return ServerConnectionIndicator(
      child: Scaffold(
        appBar: AppBar(title: const Text('Call History')),
        body: StreamBuilder<List<CallHistoryEntry>>(
          stream: service.callHistoryStream,
          builder: (context, snapshot) {
            switch (snapshot.connectionState) {
              case ConnectionState.waiting:
                _log.d('🕒 Waiting for call history data…');
                return const Center(child: CircularProgressIndicator());
              case ConnectionState.active:
              case ConnectionState.done:
                if (snapshot.hasError) {
                  _log.e('❌ Error loading call history: ${snapshot.error}');
                  return Center(child: Text('Error: ${snapshot.error}'));
                }
                final entries = snapshot.data ?? [];
                _log.i('✅ Loaded ${entries.length} call history entries');
                if (entries.isEmpty) {
                  return const Center(child: Text('No calls yet.'));
                }
                return ListView.separated(
                  separatorBuilder: (_, __) => const Divider(),
                  itemCount: entries.length,
                  itemBuilder: (context, index) {
                    final entry = entries[index];
                    final isCaller = entry.callerId == userId;
                    entry.type = isCaller ? CallType.outgoing : CallType.incoming;
                    final contactId = isCaller ? entry.calleeId : entry.callerId;
                    final contacts = ref.read(contactsProvider(userId)).contacts;
                    final contact = contacts.firstWhereOrNull((c) => c.userId == contactId);

                    return ListTile(
                      onTap: () {
                        _log.i('📝 Viewing transcript for call ${entry.id}');
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => CallTranscriptPage(
                              entry: entry,
                              localUserId: userId,
                            ),
                          ),
                        );
                      },
                      leading: Icon(_callTypeIcon(entry.type)),
                      title: Text(contact?.name ?? 'Unknown'),
                      subtitle: Text(
                        '${DateFormat.yMMMd().add_Hm().format(entry.startedAt)} '
                        '(${_formatDuration(entry.duration)})',
                      ),
                      trailing: Text(
                        entry.type.name.toUpperCase(),
                        style: TextStyle(
                          color: entry.type == CallType.missed ? Colors.red : Colors.grey,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    );
                  },
                );
              case ConnectionState.none:
                _log.e('❌ No connection to call history stream');
                return const Center(child: Text('No connection to call history stream.'));
            }
          },
        ),
      ),
    );
  }

  IconData _callTypeIcon(CallType type) {
    switch (type) {
      case CallType.incoming:
        return Icons.call_received;
      case CallType.outgoing:
        return Icons.call_made;
      case CallType.missed:
        return Icons.call_missed;
      case CallType.unknown:
        return Icons.call;
    }
  }

  String _formatDuration(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')} mins';
  }
}
