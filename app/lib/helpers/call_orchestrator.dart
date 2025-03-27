// File: call_orchestrator.dart
import 'dart:async';
import 'dart:convert';
import 'package:collection/collection.dart';
import 'package:flutter/material.dart';

import 'server_helper.dart';
import 'video_call_manager.dart';
import 'call_control_manager.dart';
import '../models/lip_c_user.dart';
import '../models/connection_target.dart';

class CallOrchestrator {
  final LipCUser localUser;
  LipCUser? remoteUser;
  final ServerHelper serverHelper;
  List<LipCUser> contacts;
  final BuildContext context;

  late final VideoCallManager videoCallManager;
  late final CallControlManager callControlManager;

  CallOrchestrator({
    required this.context,
    required this.localUser,
    required this.serverHelper,
    required this.contacts,
  }) {
    // Initialize the managers.
    videoCallManager = VideoCallManager(
      serverHelper: serverHelper,
      localUser: localUser,
      remoteUser: remoteUser,
    );

    callControlManager = CallControlManager(
      context: context,
      serverHelper: serverHelper,
      localUser: localUser,
      contacts: contacts,
      onCallAccepted: (data) async {
        remoteUser = contacts.firstWhereOrNull(
          (contact) => contact.userId == data["from"],
        );
        videoCallManager.setRemoteUser(remoteUser!);

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
      print(data);

      final String messageType = data["type"];
      final String messageFrom = data["from"] ?? "";

      switch (messageType) {
        case "call_invite":
          // Call invites are for peer connections.
          print("CallOrchestrator: Received call invite from $messageFrom");
          callControlManager.onCallInvite(data);

          break;
        case "call_accept":
          // Accept messages for peer connection.
          print("CallOrchestrator: Received call accept from $messageFrom");
          callControlManager.onCallEstablished(data, videoCallManager);

          await videoCallManager.setupCallEnvironment(ConnectionTarget.peer);
          await videoCallManager.negotiateCall(ConnectionTarget.peer,
              isCaller: true);

          await videoCallManager.setupCallEnvironment(ConnectionTarget.server);
          await videoCallManager.negotiateCall(ConnectionTarget.server,
              isCaller: true);

          break;
        case "call_reject":
          print("CallOrchestrator: Received call reject from $messageFrom");
          callControlManager.onCallReject(data);
          break;
        case "video_state":
          // Handle video state changes.
          if (!data["success"]) {
            print(
                "CallOrchestrator: Failed to update video state for $messageFrom because: ${data["reason"]}");
          } else {
            // Handle the video status update.
            bool isVideoOn = data["video"];
            print(
                "CallOrchestrator: Received video state ($isVideoOn) from $messageFrom");
            videoCallManager.updateRemoteVideoStatus(isVideoOn);
          }
          break;
        case "ice_candidate":
          print("CallOrchestrator: Received ICE candidate from $messageFrom");
          // Route ICE candidates based on target.
          if (messageFrom == "server") {
            await videoCallManager.onReceiveIceCandidate(
                ConnectionTarget.server, data["payload"]);
          } else {
            await videoCallManager.onReceiveIceCandidate(
                ConnectionTarget.peer, data["payload"]);
          }
          break;
        case "offer":
          print("CallOrchestrator: Received offer from $messageFrom");
          // Handle SDP offers.
          if (messageFrom == "server") {
            await videoCallManager.onReceiveOffer(
                ConnectionTarget.server, data["payload"]);
          } else {
            await videoCallManager.onReceiveOffer(
                ConnectionTarget.peer, data["payload"]);
            // We need to initiate a call with the server ourselves.
            await videoCallManager.negotiateCall(ConnectionTarget.server,
                isCaller: true);
          }
          break;
        case "answer":
          print("CallOrchestrator: Received answer from $messageFrom");
          // Handle SDP answers.
          if (messageFrom == "server") {
            await videoCallManager.onReceiveAnswer(
                ConnectionTarget.server, data["payload"]);
          } else {
            await videoCallManager.onReceiveAnswer(
                ConnectionTarget.peer, data["payload"]);
          }
          break;
        default:
          print("CallOrchestrator: Unhandled message type: $messageType");
      }
    });
  }

  /// Starts the call by initializing the peer connection.
  Future<void> callUser(LipCUser remoteUser) async {
    print("CallOrchestrator: Calling ${remoteUser.userId}");
    this.remoteUser = remoteUser;
    videoCallManager.setRemoteUser(remoteUser);
    // Send the call invite.
    callControlManager.sendCallInvite(remoteUser);
  }

  void updateContacts(List<LipCUser> newContacts) {
    contacts = newContacts;
    callControlManager.updateContacts(newContacts);
  }

  /// Dispose of the orchestrator and its underlying managers.
  void dispose() {
    videoCallManager.dispose();
  }
}
