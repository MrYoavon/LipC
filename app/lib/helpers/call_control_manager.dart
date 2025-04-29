// lib/helpers/call_control_manager.dart

import 'package:flutter/material.dart';
import 'package:lip_c/constants.dart';
import 'package:lip_c/helpers/video_call_manager.dart';
import 'package:lip_c/models/lip_c_user.dart';
import 'package:collection/collection.dart';
import 'package:lip_c/pages/incoming_call_page.dart';
import 'package:logger/logger.dart';

import '../pages/call_page.dart';
import 'server_helper.dart';
import 'app_logger.dart';

class CallControlManager {
  final Logger _log = AppLogger.instance;

  BuildContext context;
  final ServerHelper serverHelper;
  final LipCUser localUser;
  List<LipCUser> contacts;
  final Future<void> Function(Map<String, dynamic> data) onCallAccepted;

  CallControlManager({
    required this.context,
    required this.serverHelper,
    required this.localUser,
    required this.contacts,
    required this.onCallAccepted,
  }) {
    _log.i('📞 CallControlManager initialized for user ${localUser.username}');
  }

  /// Sends a call invitation to the remote user.
  void sendCallInvite(LipCUser remoteUser) {
    _log.i('📤 Sending call invite to ${remoteUser.username}');
    serverHelper.sendMessage(
      msgType: "call_invite",
      payload: {
        "from": localUser.userId,
        "target": remoteUser.userId,
      },
    );
  }

  /// Handles an incoming call invite message.
  void onCallInvite(Map<String, dynamic> data) {
    if (data["success"] == false) {
      final String errCode = data["error_code"];
      final String errMsg = data["error_message"];
      _log.w('⚠️ Call invite failed: $errCode | $errMsg');
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: errCode == "TARGET_NOT_AVAILABLE"
              ? Text(
                  "Call invite failed: ${findContact(errMsg.split(" ")[0])?.username ?? errMsg.split(" ")[0]} is not available") // Up until the first space is the userId
              : Text("Call invite failed: $errMsg"),
          backgroundColor: AppColors.accent,
          padding: EdgeInsets.symmetric(vertical: 8, horizontal: 16),
          behavior: SnackBarBehavior.floating,
          duration: Duration(seconds: 2),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      );
      return;
    }

    final Map<String, dynamic> payload = data["payload"] as Map<String, dynamic>;
    final String invitingUserId = payload["from"] as String;
    _log.i('📨 Received call invite from $invitingUserId');

    final LipCUser? remoteUser = findContact(invitingUserId);
    if (remoteUser == null) {
      _log.e('❌ Inviting user not in contacts: $invitingUserId');
      return;
    }

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => IncomingCallPage(
          remoteUser: remoteUser,
          callData: data,
          onReject: () {
            _log.i('✖️ Rejecting call from $invitingUserId');
            Navigator.pop(context);
            sendCallReject(data);
          },
          onAccept: () async {
            _log.i('✅ Accepting call from $invitingUserId');
            Navigator.pop(context);
            await onCallAccepted(data);
          },
        ),
      ),
    );
  }

  /// Sends a call acceptance response.
  void sendCallAccept(Map<String, dynamic> data) {
    final String invitingUserId = (data["payload"] as Map<String, dynamic>)["from"] as String;
    _log.i('📤 Sending call accept to $invitingUserId');
    serverHelper.sendMessage(
      msgType: "call_accept",
      payload: {
        "from": localUser.userId,
        "target": invitingUserId,
      },
    );
  }

  /// Sends a call rejection response.
  void sendCallReject(Map<String, dynamic> data) {
    final String invitingUserId = (data["payload"] as Map<String, dynamic>)["from"] as String;
    _log.i('📤 Sending call reject to $invitingUserId');
    serverHelper.sendMessage(
      msgType: "call_reject",
      payload: {
        "from": localUser.userId,
        "target": invitingUserId,
      },
    );
  }

  /// Handles an incoming call rejection.
  void onCallReject(Map<String, dynamic> data) {
    final Map<String, dynamic> payload = data["payload"] as Map<String, dynamic>;
    final String fromId = payload["from"] as String;
    final LipCUser? callee = findContact(fromId);
    final String username = callee?.username ?? fromId;
    _log.i('✖️ Call rejected by $username');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text("Call rejected by $username"),
        backgroundColor: AppColors.accent,
        padding: EdgeInsets.symmetric(vertical: 8, horizontal: 16),
        behavior: SnackBarBehavior.floating,
        duration: Duration(seconds: 2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  /// Sends a call end notification.
  void sendCallEnd(String targetUserId) {
    _log.i('📤 Sending call end to $targetUserId');
    serverHelper.sendMessage(
      msgType: "call_end",
      payload: {
        "from": localUser.userId,
        "target": targetUserId,
      },
    );
  }

  /// Handles an incoming call end notification.
  void onCallEnd(Map<String, dynamic> data) {
    final String fromId = (data["payload"] as Map<String, dynamic>)["from"] as String;
    final LipCUser? disconnectingUser = findContact(fromId);
    final String name = disconnectingUser?.name ?? fromId;
    _log.i('📤 Call ended by $name');
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text("Call ended by $name")),
    );
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  /// Navigates to the CallPage after the call is established.
  void navigateToCallPage(
    Map<String, dynamic> data,
    VideoCallManager videoCallManager, {
    bool isCaller = false,
  }) {
    final callingUserId = (data["payload"] as Map<String, dynamic>)["from"] as String;
    _log.i('📤 Call established with $callingUserId');
    if (isCaller) Navigator.pop(context);

    final remote = findContact(callingUserId);
    if (remote == null) {
      _log.e('❌ Calling user not in contacts: $callingUserId');
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => CallPage(
          localUser: localUser,
          remoteUser: remote,
          serverHelper: serverHelper,
          videoCallManager: videoCallManager,
        ),
      ),
    );
  }

  /// Updates the internal contacts list.
  void updateContacts(List<LipCUser> newContacts) {
    _log.d('🔄 Contacts list updated (${newContacts.length} entries)');
    contacts = newContacts;
  }

  /// Finds a contact by user ID.
  LipCUser? findContact(String userId) {
    return contacts.firstWhereOrNull((c) => c.userId == userId);
  }
}
