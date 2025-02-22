// File: call_orchestrator.dart
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'server_helper.dart';
import 'video_call_manager.dart';
import 'call_control_manager.dart';

class CallOrchestrator {
  final ServerHelper serverHelper;
  final String localUsername;
  String remoteUsername = ""; // The username of the remote peer.
  final BuildContext context;

  late final VideoCallManager videoCallManager;
  late final CallControlManager callControlManager;

  CallOrchestrator({
    required this.serverHelper,
    required this.localUsername,
    required this.context,
  }) {
    // Initialize the managers
    videoCallManager = VideoCallManager(
      serverHelper: serverHelper,
      localUsername: localUsername,
      remoteUsername: remoteUsername,
    );

    callControlManager = CallControlManager(
      serverHelper: serverHelper,
      localUsername: localUsername,
      context: context,
      onCallAccepted: (data) async {
        callControlManager.onCallEstablished(data, videoCallManager);
        // Set up the call environment.
        await videoCallManager.setupCallEnvironment();
        // Send call acceptance.
        callControlManager.sendCallAccept(data);
      },
    );

    // Start listening to signaling messages and route them appropriately.
    serverHelper.messages.listen((message) async {
      print("CallOrchestrator received message: $message");
      final data = jsonDecode(message);

      switch (data["type"]) {
        case "call_invite":
          if (data["target"] == localUsername) {
            print(
                "CallOrchestrator: Received call invite from ${data["from"]}");
            videoCallManager.remoteUsername = data[
                "from"]; // Set the remote username because initially it's set to an empty string ('')
            callControlManager.onCallInvite(data);
          }
          break;
        case "call_accept":
          print("CallOrchestrator: Received call accept from ${data["from"]}");
          if (data["target"] == localUsername) {
            callControlManager.onCallEstablished(data, videoCallManager);
            await videoCallManager.setupCallEnvironment();
            await videoCallManager.negotiateCall(isCaller: true);
          }
          break;
        case "call_reject":
          print("CallOrchestrator: Received call reject from ${data["from"]}");
          if (data["target"] == localUsername) {
            callControlManager.onCallReject(data);
          }
          break;
        case "ice_candidate":
          if (data["target"] == localUsername) {
            await videoCallManager.onReceiveIceCandidate(data["payload"]);
          }
          break;
        case "offer":
          if (data["target"] == localUsername) {
            print("CallOrchestrator: Received offer from ${data["from"]}");
            await videoCallManager.onReceiveOffer(data["payload"]);
          }
          break;
        case "answer":
          if (data["target"] == localUsername) {
            print("CallOrchestrator: Received answer from ${data["from"]}");
            await videoCallManager.onReceiveAnswer(data["payload"]);
          }
          break;
        default:
          print("CallOrchestrator: Unhandled message type: ${data["type"]}");
      }
    });
  }

  /// Starts the call by initializing the video connection.
  Future<void> callUser(String remoteUsername) async {
    this.remoteUsername = remoteUsername;
    videoCallManager.remoteUsername = remoteUsername;
    // Send the call invite.
    callControlManager.sendCallInvite(remoteUsername);
    print("CallOrchestrator: Sent call invite to $remoteUsername");
  }

  /// Dispose of the orchestrator and its underlying managers.
  void dispose() {
    videoCallManager.dispose();
  }
}
