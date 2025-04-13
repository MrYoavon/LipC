// File: helpers/call_control_manager.dart
import 'package:flutter/material.dart';
import 'package:lip_c/constants.dart';
import 'package:lip_c/helpers/video_call_manager.dart';
import 'package:lip_c/models/lip_c_user.dart';
import 'package:collection/collection.dart';
import 'package:lip_c/pages/incoming_call_page.dart';

import '../pages/call_page.dart';
import 'server_helper.dart';

class CallControlManager {
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
  });

  // Send a call invitation.
  void sendCallInvite(LipCUser remoteUser) {
    print("Sending call invite to ${remoteUser.username}");
    serverHelper.sendMessage(
      msgType: "call_invite",
      payload: {
        "from": localUser.userId,
        "target": remoteUser.userId,
      },
    );
  }

  // Callback for incoming call invites.
  void onCallInvite(Map<String, dynamic> data) {
    if (data["success"] == false) {
      print("Call invite failed: ${data["error_code"]} | ${data["error_message"]}");
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Call invite failed: ${data["error_message"]}"),
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

    final payload = data["payload"];
    final String invitingUserId = payload["from"];
    print("Received call invite from $invitingUserId");

    // Find the remote user in the contacts list.
    final LipCUser? remoteUser = findContact(invitingUserId);

    // Navigate to the IncomingCallScreen instead of showing a dialog.
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => IncomingCallPage(
          remoteUser: remoteUser!,
          callData: data,
          onReject: () {
            Navigator.pop(context);
            sendCallReject(data);
          },
          onAccept: () async {
            Navigator.pop(context);
            await onCallAccepted(data);
          },
        ),
      ),
    );
  }

  // Send a call acceptance.
  void sendCallAccept(Map<String, dynamic> data) {
    final payload = data["payload"];
    final String invitingUserId = payload["from"];
    print("Sending call accept to $invitingUserId");
    serverHelper.sendMessage(
      msgType: "call_accept",
      payload: {
        "from": localUser.userId,
        "target": invitingUserId,
      },
    );
  }

  // Send a call rejection.
  void sendCallReject(Map<String, dynamic> data) {
    final payload = data["payload"];
    final String invitingUserId = payload["from"];
    print("Sending call reject to $invitingUserId");
    serverHelper.sendMessage(
      msgType: "call_reject",
      payload: {
        "from": localUser.userId,
        "target": invitingUserId,
      },
    );
  }

  void onCallReject(Map<String, dynamic> data) {
    final payload = data["payload"];
    final LipCUser? callee = findContact(payload["from"]);

    print("Call rejected by ${callee?.username ?? payload["from"]}"); // Display the userId if not found
    // Show a message to the user
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text("Call rejected by ${callee?.username ?? payload["from"]}"),
        backgroundColor: AppColors.accent,
        padding: EdgeInsets.symmetric(vertical: 8, horizontal: 16),
        behavior: SnackBarBehavior.floating,
        duration: Duration(seconds: 2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );

    // If you are on the CallingPage, pop it:
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  void sendCallEnd(String targetUserId) {
    print("Sending call end to $targetUserId");
    serverHelper.sendMessage(
      msgType: "call_end",
      payload: {
        "from": localUser.userId,
        "target": targetUserId,
      },
    );
  }

  void onCallEnd(Map<String, dynamic> data) {
    final payload = data["payload"];
    final String disconnectingUserId = payload["from"];
    final LipCUser? disconnectingUser = findContact(disconnectingUserId);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text("Call ended by ${disconnectingUser?.name ?? disconnectingUserId}")),
    );
    // If you are on the CallPage, pop it:
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  void navigateToCallPage(Map<String, dynamic> data, VideoCallManager videoCallManager, {bool isCaller = false}) {
    final payload = data["payload"];
    final String callingUserId = payload["from"];
    print("Call established with $callingUserId");
    // Pop out of the calling page if caller
    if (isCaller) {
      Navigator.pop(context);
    }

    // Navigate to the call page
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => CallPage(
          localUser: localUser,
          remoteUser: findContact(callingUserId)!,
          serverHelper: serverHelper,
          videoCallManager: videoCallManager,
        ),
      ),
    );
  }

  void updateContacts(List<LipCUser> newContacts) {
    contacts = newContacts;
  }

  LipCUser? findContact(String userId) {
    return contacts.firstWhereOrNull((contact) => contact.userId == userId);
  }
}
