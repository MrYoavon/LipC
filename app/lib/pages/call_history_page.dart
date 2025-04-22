import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:lip_c/widgets/server_connection_indicator.dart';

import '../models/call_history_entry.dart';
import '../helpers/call_history_service.dart';
import '../providers/contacts_provider.dart';
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
    service.requestCallHistory(userId);

    return ServerConnectionIndicator(
      child: Scaffold(
        appBar: AppBar(title: const Text('Call History')),
        body: StreamBuilder<List<CallHistoryEntry>>(
          stream: service.callHistoryStream,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(child: Text('Error: ${snapshot.error}'));
            }
            final entries = snapshot.data ?? [];
            if (entries.isEmpty) {
              return const Center(child: Text('No calls yet.'));
            }

            return ListView.separated(
              separatorBuilder: (_, __) => const Divider(),
              itemCount: entries.length,
              itemBuilder: (context, index) {
                final entry = entries[index];
                final bool isCaller = entry.callerId == userId;
                final String contactId = isCaller ? entry.calleeId : entry.callerId;
                final contacts = ref.read(contactsProvider(userId)).contacts;
                final contact = contacts.firstWhereOrNull(
                  (contact) => contact.userId == contactId,
                );
                entry.type = isCaller ? CallType.outgoing : CallType.incoming;

                return ListTile(
                  onTap: () {
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
