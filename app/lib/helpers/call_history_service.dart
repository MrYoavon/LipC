// lib/helpers/call_history_service.dart

import 'dart:async';
import 'dart:convert';
import 'package:logger/logger.dart';

import 'server_helper.dart';
import 'app_logger.dart';
import '../models/call_history_entry.dart';

class CallHistoryService {
  final Logger _log = AppLogger.instance;
  final ServerHelper serverHelper;

  CallHistoryService({required this.serverHelper}) {
    _log.i('📅 CallHistoryService initialized');
  }

  /// Requests call history for the given user with an optional limit.
  void requestCallHistory(String userId, {int limit = 50}) {
    _log.i('📨 Requesting call history for user: $userId (limit: $limit)');
    serverHelper.sendMessage(
      msgType: "fetch_call_history",
      payload: {
        'user_id': userId,
        'limit': limit,
      },
    );
  }

  /// Stream of call history entries parsed from server messages.
  Stream<List<CallHistoryEntry>> get callHistoryStream {
    _log.d('🌐 Subscribing to call history stream');
    return serverHelper.messages
        .map((event) => jsonDecode(event))
        .where((event) => event['msg_type'] == 'fetch_call_history')
        .map<List<CallHistoryEntry>>((event) {
      try {
        final List<dynamic> entriesJson = event['payload']['entries'] as List<dynamic>;
        final entries = entriesJson.map((e) => CallHistoryEntry.fromJson(e as Map<String, dynamic>)).toList();
        _log.i('✅ Received ${entries.length} call history entries');
        return entries;
      } catch (e, st) {
        _log.e('❌ Error parsing call history entries', error: e, stackTrace: st);
        return <CallHistoryEntry>[];
      }
    });
  }
}
