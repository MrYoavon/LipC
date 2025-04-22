import 'dart:convert';

import '../models/call_history_entry.dart';
import 'server_helper.dart';

class CallHistoryService {
  final ServerHelper serverHelper;

  CallHistoryService({required this.serverHelper});

  void requestCallHistory(String userId, {int limit = 50}) {
    serverHelper.sendMessage(
      msgType: "fetch_call_history",
      payload: {
        'user_id': userId,
        'limit': limit,
      },
    );
  }

  Stream<List<CallHistoryEntry>> get callHistoryStream {
    return serverHelper.messages
        .map((event) => jsonDecode(event))
        .where((event) => event['msg_type'] == 'fetch_call_history')
        .map((event) {
      final entries = event["payload"]['entries'] as List<dynamic>;
      return entries.map((e) => CallHistoryEntry.fromJson(e)).toList();
    });
  }
}
