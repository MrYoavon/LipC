// lib/helpers/call_orchestrator.dart

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:collection/collection.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../pages/outgoing_call_page.dart';
import '../providers/subtitles_provider.dart';
import 'server_helper.dart';
import 'video_call_manager.dart';
import 'call_control_manager.dart';
import '../models/lip_c_user.dart';
import '../models/connection_target.dart';
import 'app_logger.dart';

class CallOrchestrator {
  final Logger _log = AppLogger.instance;
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
    _log.i('🎯 CallOrchestrator initialized for ${localUser.username}');

    callControlManager = CallControlManager(
      context: context,
      serverHelper: serverHelper,
      localUser: localUser,
      contacts: contacts,
      onCallAccepted: (data) async {
        final payload = data['payload'];
        final fromId = payload['from'];
        remoteUser = contacts.firstWhereOrNull((c) => c.userId == fromId);
        if (remoteUser == null) {
          _log.e('❌ Remote user not found: $fromId');
          return;
        }

        videoCallManager = VideoCallManager(
          serverHelper: serverHelper,
          localUser: localUser,
          remoteUser: remoteUser,
        );

        _log.i('➡️ Navigating to CallPage as callee');
        callControlManager.navigateToCallPage(data, videoCallManager!, isCaller: false);

        _log.i('🔧 Setting up peer environment for peer');
        await videoCallManager?.setupCallEnvironment(ConnectionTarget.peer);

        _log.i('📤 Sending call accept');
        callControlManager.sendCallAccept(data);

        _log.i('🔧 Setting up peer environment for server');
        await videoCallManager?.setupCallEnvironment(ConnectionTarget.server);
      },
    );

    serverHelper.messages.listen((message) async {
      final data = jsonDecode(message);
      final msgType = data['msg_type'];
      final payload = data['payload'];
      final fromId = payload['from'] ?? '';
      _log.d('📩 Received message: $msgType from $fromId');

      switch (msgType) {
        case 'call_invite':
          _log.i('📨 Received call invite from $fromId');
          callControlManager.onCallInvite(data);
          break;
        case 'call_accept':
          _log.i('✅ Received call accept from $fromId');
          callControlManager.navigateToCallPage(data, videoCallManager!, isCaller: true);
          sleep(const Duration(milliseconds: 1000));
          await videoCallManager?.setupCallEnvironment(ConnectionTarget.peer);
          await videoCallManager?.setupCallEnvironment(ConnectionTarget.server);
          await videoCallManager?.negotiateCall(ConnectionTarget.peer, isCaller: true);
          await videoCallManager?.negotiateCall(ConnectionTarget.server, isCaller: true);
          break;
        case 'call_reject':
          _log.i('✖️ Received call reject from $fromId');
          callControlManager.onCallReject(data);
          break;
        case 'video_state':
          if (!data['success']) {
            final err = data['error_message'];
            _log.w('⚠️ Video state update failed from $fromId: $err');
          } else {
            final isVideoOn = payload['video'] as bool;
            _log.d('📷 Received video state from $fromId: $isVideoOn');
            videoCallManager?.updateRemoteVideoStatus(isVideoOn);
          }
          break;
        case 'call_end':
          _log.i('📴 Received call end from $fromId');
          callControlManager.onCallEnd(data);
          videoCallManager?.dispose();
          break;
        case 'ice_candidate':
          _log.d('🌐 Received ICE candidate from $fromId');
          if (fromId == 'server') {
            await videoCallManager?.onReceiveIceCandidate(ConnectionTarget.server, data['payload']['candidate']);
          } else {
            await videoCallManager?.onReceiveIceCandidate(ConnectionTarget.peer, data['payload']['candidate']);
          }
          break;
        case 'offer':
          _log.i('📨 Received offer from $fromId');
          if (fromId == 'server') {
            await videoCallManager?.onReceiveOffer(ConnectionTarget.server, data['payload']['offer']);
          } else {
            await videoCallManager?.onReceiveOffer(ConnectionTarget.peer, data['payload']['offer']);
            await videoCallManager?.negotiateCall(ConnectionTarget.server, isCaller: true);
          }
          break;
        case 'answer':
          _log.i('📨 Received answer from $fromId');
          if (fromId == 'server') {
            await videoCallManager?.onReceiveAnswer(ConnectionTarget.server, data['payload']['answer']);
          } else {
            await videoCallManager?.onReceiveAnswer(ConnectionTarget.peer, data['payload']['answer']);
          }
          break;
        case 'lip_reading_prediction':
          _log.d('🤖 Received lip reading prediction from $fromId');
          final prediction = payload['prediction'] as String? ?? '';
          ProviderScope.containerOf(context, listen: false).read(subtitlesProvider.notifier).update(prediction);
          break;
        default:
          _log.w('❓ Unhandled message type: $msgType');
      }
    });
  }

  /// Starts an outgoing call to the given user.
  Future<void> callUser(LipCUser remote) async {
    _log.i('📞 Calling user ${remote.userId}');
    videoCallManager = VideoCallManager(
      serverHelper: serverHelper,
      localUser: localUser,
      remoteUser: remote,
    );
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => OutgoingCallPage(remoteUser: remote)),
    );
    callControlManager.sendCallInvite(remote);
  }

  /// Updates the internal contacts list.
  void updateContacts(List<LipCUser> newContacts) {
    _log.d('🔄 Contacts updated: ${newContacts.length} entries');
    contacts = newContacts;
    callControlManager.updateContacts(newContacts);
  }

  /// Disposes of resources when done.
  void dispose() {
    _log.i('🗑️ Disposing CallOrchestrator');
    videoCallManager?.dispose();
  }
}
