// File: call_orchestrator.dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';
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

  VideoCallManager? videoCallManager;
  late final CallControlManager callControlManager;

  CallOrchestrator({
    required this.context,
    required this.localUser,
    required this.serverHelper,
    required this.contacts,
  }) {
    // // Initialize the managers.
    // videoCallManager = VideoCallManager(
    //   serverHelper: serverHelper,
    //   localUser: localUser,
    //   remoteUser: null,
    // );

    callControlManager = CallControlManager(
      context: context,
      serverHelper: serverHelper,
      localUser: localUser,
      contacts: contacts,
      onCallAccepted: (data) async {
        remoteUser = contacts.firstWhereOrNull(
          (contact) => contact.userId == data["from"],
        );
        if (remoteUser == null) {
          print("CallOrchestrator: Remote user not found in contacts.");
          return;
        }

        // Create a brand-new manager for this call
        videoCallManager = VideoCallManager(
          serverHelper: serverHelper,
          localUser: localUser,
          remoteUser: remoteUser,
        );

        // 1. Send the user to the call page.
        callControlManager.navigateToCallPage(data, videoCallManager!);

        // 2. When the call is accepted, first establish the peer connection.
        await videoCallManager?.setupCallEnvironment(ConnectionTarget.peer);

        // 3. Send call acceptance.
        callControlManager.sendCallAccept(data);

        // 4. Establish the server connection.
        await videoCallManager?.setupCallEnvironment(ConnectionTarget.server);
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

          callControlManager.navigateToCallPage(data, videoCallManager!);
          sleep(Duration(milliseconds: 1000));

          await videoCallManager?.setupCallEnvironment(ConnectionTarget.peer);
          await videoCallManager?.setupCallEnvironment(ConnectionTarget.server);

          await videoCallManager?.negotiateCall(ConnectionTarget.peer,
              isCaller: true);
          await videoCallManager?.negotiateCall(ConnectionTarget.server,
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
            videoCallManager?.updateRemoteVideoStatus(isVideoOn);
          }
          break;
        case "call_end":
          print("CallOrchestrator: Received call end from $messageFrom");
          callControlManager.onCallEnd(data);
          videoCallManager?.dispose();
          break;
        case "ice_candidate":
          print("CallOrchestrator: Received ICE candidate from $messageFrom");
          // Route ICE candidates based on target.
          if (messageFrom == "server") {
            await videoCallManager?.onReceiveIceCandidate(
                ConnectionTarget.server, data["payload"]);
          } else {
            await videoCallManager?.onReceiveIceCandidate(
                ConnectionTarget.peer, data["payload"]);
          }
          break;
        case "offer":
          print("CallOrchestrator: Received offer from $messageFrom");
          // Handle SDP offers.
          if (messageFrom == "server") {
            await videoCallManager?.onReceiveOffer(
                ConnectionTarget.server, data["payload"]);
          } else {
            await videoCallManager?.onReceiveOffer(
                ConnectionTarget.peer, data["payload"]);
            // We need to initiate a call with the server ourselves.
            await videoCallManager?.negotiateCall(ConnectionTarget.server,
                isCaller: true);
          }
          break;
        case "answer":
          print("CallOrchestrator: Received answer from $messageFrom");
          // Handle SDP answers.
          if (messageFrom == "server") {
            await videoCallManager?.onReceiveAnswer(
                ConnectionTarget.server, data["payload"]);
          } else {
            await videoCallManager?.onReceiveAnswer(
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
    // Create a brand-new manager for this call
    videoCallManager = VideoCallManager(
      serverHelper: serverHelper,
      localUser: localUser,
      remoteUser: remoteUser,
    );

    // Proceed with the invite
    callControlManager.sendCallInvite(remoteUser);
  }

  void updateContacts(List<LipCUser> newContacts) {
    contacts = newContacts;
    callControlManager.updateContacts(newContacts);
  }

  /// Dispose of the orchestrator and its underlying managers.
  void dispose() {
    videoCallManager?.dispose();
  }
}
