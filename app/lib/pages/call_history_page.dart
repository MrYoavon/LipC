import 'package:flutter/material.dart';
import '../models/call_history_entry.dart';
import '../helpers/call_history_service.dart';

class CallHistoryPage extends StatelessWidget {
  final CallHistoryService service;
  final String userId;

  const CallHistoryPage({
    super.key,
    required this.service,
    required this.userId,
  });

  @override
  Widget build(BuildContext context) {
    service.requestCallHistory(userId);

    return Scaffold(
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
              return ListTile(
                leading: Icon(_callTypeIcon(entry.type)),
                title: Text(entry.contactName),
                subtitle: Text(
                  '${entry.timestamp.toLocal()} (${_formatDuration(entry.duration)})',
                ),
                trailing: Text(
                  entry.type.name.toUpperCase(),
                  style: TextStyle(
                    color: entry.type == CallType.missed
                        ? Colors.red
                        : Colors.grey,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              );
            },
          );
        },
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
    }
  }

  String _formatDuration(Duration duration) {
    final minutes = duration.inMinutes;
    final seconds = duration.inSeconds % 60;
    return '$minutes:${seconds.toString().padLeft(2, '0')} mins';
  }
}
