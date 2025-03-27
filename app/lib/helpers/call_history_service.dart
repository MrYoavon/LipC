import 'dart:convert';

import '../models/call_history_entry.dart';
import 'server_helper.dart';

class CallHistoryService {
  final ServerHelper serverHelper;

  CallHistoryService({required ServerHelper serverHelper})
      : this.serverHelper = serverHelper;

  void requestCallHistory(String userId, {int limit = 50}) {
    final request = {
      'type': 'fetch_call_history',
      'user_id': userId,
      'limit': limit,
    };
    serverHelper.sendRawMessage(request);
  }

  Stream<List<CallHistoryEntry>> get callHistoryStream {
    return serverHelper.messages
        .map((event) => jsonDecode(event))
        .where((event) => event['type'] == 'call_history')
        .map((event) {
      final entries = event['entries'] as List<dynamic>;
      return entries.map((e) => CallHistoryEntry.fromJson(e)).toList();
    });
  }
}
