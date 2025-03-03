// File: call_orchestrator.dart
import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'server_helper.dart';
import 'video_call_manager.dart';
import 'call_control_manager.dart';
import '../models/connection_target.dart'; // Shared enum

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
    // Initialize the managers.
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
        // Send the user to the call page.
        callControlManager.onCallEstablished(data, videoCallManager);

        // When the call is accepted, first establish the peer connection.
        await videoCallManager.setupCallEnvironment(ConnectionTarget.peer);

        // Establish the server connection.
        await videoCallManager.setupCallEnvironment(ConnectionTarget.server);

        // Send call acceptance.
        callControlManager.sendCallAccept(data);
      },
    );

    // Listen to signaling messages and route them appropriately.
    serverHelper.messages.listen((message) async {
      final data = jsonDecode(message);

      final String messageType = data["type"];
      final String messageTarget = data["target"] ?? "";
      final String messageFrom = data["from"] ?? "";

      switch (messageType) {
        case "call_invite":
          // Call invites are for peer connections.
          if (messageTarget == localUsername) {
            print(
                "CallOrchestrator: Received call invite from ${data["from"]}");
            videoCallManager.remoteUsername =
                data["from"]; // Set remote username.
            callControlManager.onCallInvite(data);
          }
          break;
        case "call_accept":
          // Accept messages for peer connection.
          if (messageTarget == localUsername) {
            print(
                "CallOrchestrator: Received call accept from ${data["from"]}");
            callControlManager.onCallEstablished(data, videoCallManager);

            await videoCallManager.setupCallEnvironment(ConnectionTarget.peer);
            await videoCallManager.negotiateCall(ConnectionTarget.peer,
                isCaller: true);

            await videoCallManager
                .setupCallEnvironment(ConnectionTarget.server);
            await videoCallManager.negotiateCall(ConnectionTarget.server,
                isCaller: true);
          }
          break;
        case "call_reject":
          if (messageTarget == localUsername) {
            print(
                "CallOrchestrator: Received call reject from ${data["from"]}");
            callControlManager.onCallReject(data);
          }
          break;
        case "ice_candidate":
          // Route ICE candidates based on target.
          if (messageFrom == "server") {
            print(
                "CallOrchestrator: Received server ICE candidate from ${data["from"]}");
            await videoCallManager.onReceiveIceCandidate(
                ConnectionTarget.server, data["payload"]);
          } else {
            print(
                "CallOrchestrator: Received ICE candidate from ${data["from"]}");
            await videoCallManager.onReceiveIceCandidate(
                ConnectionTarget.peer, data["payload"]);
          }
          break;
        case "offer":
          // Handle SDP offers.
          if (messageFrom == "server") {
            print(
                "CallOrchestrator: Received server offer from ${data["from"]}");
            await videoCallManager.onReceiveOffer(
                ConnectionTarget.server, data["payload"]);
          } else {
            print("CallOrchestrator: Received offer from ${data["from"]}");
            await videoCallManager.onReceiveOffer(
                ConnectionTarget.peer, data["payload"]);
            await videoCallManager.negotiateCall(ConnectionTarget.server,
                isCaller: true);
          }
          break;
        case "answer":
          // Handle SDP answers.
          if (messageFrom == "server") {
            print(
                "CallOrchestrator: Received server answer from ${data["from"]}");
            await videoCallManager.onReceiveAnswer(
                ConnectionTarget.server, data["payload"]);
          } else {
            print("CallOrchestrator: Received answer from ${data["from"]}");
            await videoCallManager.onReceiveAnswer(
                ConnectionTarget.peer, data["payload"]);
          }
          break;
        default:
          print("CallOrchestrator: Unhandled message type: ${data["type"]}");
      }
    });
  }

  /// Starts the call by initializing the peer connection.
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
