// lib/pages/call_transcript_page.dart

import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../models/call_history_entry.dart';
import '../providers/contacts_provider.dart';

class CallTranscriptPage extends ConsumerWidget {
  final CallHistoryEntry entry;
  final String localUserId;
  static final Logger _log = AppLogger.instance;

  const CallTranscriptPage({
    super.key,
    required this.entry,
    required this.localUserId,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lines = entry.transcripts;
    final isCaller = entry.callerId == localUserId;
    final contactId = isCaller ? entry.calleeId : entry.callerId;
    final contacts = ref.read(contactsProvider(localUserId)).contacts;
    final contact = contacts.firstWhereOrNull((c) => c.userId == contactId);
    final contactName = contact?.name ?? contactId;

    _log.i(
      '📖 CallTranscriptPage opened for call ${entry.id} with $contactName '
      '(${lines.length} transcript lines)',
    );

    return Scaffold(
      appBar: AppBar(
        title: FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            "$contactName | ${DateFormat.yMMMd().add_Hm().format(entry.startedAt)}",
          ),
        ),
      ),
      body: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
        itemCount: lines.length,
        itemBuilder: (context, i) {
          final line = lines[i];
          final isMe = line["speaker"] == localUserId;
          final time = DateTime.parse(line["t"]);
          _log.d(
            '💬 Transcript line $i by ${line["speaker"]}: "${line["text"]}"',
          );

          return Align(
            alignment: isMe ? Alignment.centerRight : Alignment.centerLeft,
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 4),
              padding: const EdgeInsets.all(12),
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              decoration: BoxDecoration(
                color: isMe ? Theme.of(context).colorScheme.primary.withOpacity(0.8) : Colors.grey.shade200,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(isMe ? 12 : 0),
                  topRight: Radius.circular(isMe ? 0 : 12),
                  bottomLeft: const Radius.circular(12),
                  bottomRight: const Radius.circular(12),
                ),
              ),
              child: Column(
                crossAxisAlignment: isMe ? CrossAxisAlignment.end : CrossAxisAlignment.start,
                children: [
                  Text(
                    line["text"],
                    style: TextStyle(
                      color: isMe ? Colors.white : Colors.black87,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    "${time.hour.toString().padLeft(2, '0')}:"
                    "${time.minute.toString().padLeft(2, '0')}",
                    style: TextStyle(
                      color: isMe ? Colors.white70 : Colors.black45,
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
