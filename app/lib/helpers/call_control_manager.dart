// File: helpers/call_control_manager.dart
import 'package:flutter/material.dart';
import 'package:lip_c/helpers/video_call_manager.dart';
import 'package:lip_c/models/lip_c_user.dart';
import 'package:collection/collection.dart';

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

  // Callback for incoming call invites.
  void onCallInvite(Map<String, dynamic> data) {
    print("Received call invite from ${data["from"]}");

    // Find the remote user in the contacts list.
    final remoteUser = contacts.firstWhereOrNull(
      (contact) => contact.userId == data["from"],
    );

    // You can now show a dialog to accept/reject the call.
    showDialog(
      context: context,
      barrierDismissible: false, // Prevent dismissing by tapping outside
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text("Incoming Call"),
          content: Text("Call from ${remoteUser?.username ?? data["from"]}"),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop(); // Close dialog
                sendCallReject(data);
              },
              child: Text("Reject"),
            ),
            TextButton(
              onPressed: () async {
                Navigator.of(context).pop(); // Close dialog
                await onCallAccepted(data); // Delegate to orchestrator.
              },
              child: Text("Accept"),
            ),
          ],
        );
      },
    );
  }

  // Send a call invitation.
  void sendCallInvite(LipCUser remoteUser) {
    print("Sending call invite to ${remoteUser.username}");
    serverHelper.sendRawMessage({
      "type": "call_invite",
      "from": localUser.userId,
      "target": remoteUser.userId,
    });
  }

  // Send a call acceptance.
  void sendCallAccept(Map<String, dynamic> data) {
    print("Sending call accept to ${data["from"]}");
    serverHelper.sendRawMessage({
      "type": "call_accept",
      "from": localUser.userId,
      "target": data["from"],
    });
  }

  // Send a call rejection.
  void sendCallReject(Map<String, dynamic> data) {
    print("Sending call reject to ${data["from"]}");
    serverHelper.sendRawMessage({
      "type": "call_reject",
      "from": localUser.userId,
      "target": data["from"],
    });
  }

  void onCallReject(Map<String, dynamic> data) {
    print("Call rejected by ${data["from"]}");
    // Show a message to the user
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text("Call rejected by ${data["from"]}"),
      ),
    );
  }

  void onCallEstablished(
      Map<String, dynamic> data, VideoCallManager videoCallManager) {
    print("Call established with ${data["from"]}");
    // Navigate to the call page
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => CallPage(
          localUser: localUser,
          remoteUser: findContact(data["from"])!,
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
