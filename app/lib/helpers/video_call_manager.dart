// lib/helpers/video_call_manager.dart

import 'dart:async';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:logger/logger.dart';
import '../models/lip_c_user.dart';
import '../models/connection_target.dart';
import 'server_helper.dart';
import 'app_logger.dart';

class VideoCallManager {
  final Logger _log = AppLogger.instance;

  RTCPeerConnection? _peerConnection;
  RTCPeerConnection? _serverConnection;
  final List<Map<String, dynamic>> _peerPendingIceCandidates = [];
  final List<Map<String, dynamic>> _serverPendingIceCandidates = [];

  MediaStream? _localStream;
  final LipCUser localUser;
  LipCUser? remoteUser;
  final ServerHelper serverHelper;

  final _localStreamController = StreamController<MediaStream>.broadcast();
  final StreamController<bool> _localVideoStatusController = StreamController<bool>.broadcast();
  final _remoteStreamController = StreamController<MediaStream>.broadcast();
  final StreamController<bool> _remoteVideoStatusController = StreamController<bool>.broadcast();

  /// Expose the local media stream.
  Stream<MediaStream> get localStreamStream => _localStreamController.stream;
  Stream<bool> get localVideoStatusStream => _localVideoStatusController.stream;

  /// Expose the remote media stream.
  Stream<MediaStream> get remoteStreamStream => _remoteStreamController.stream;
  Stream<bool> get remoteVideoStatusStream => _remoteVideoStatusController.stream;

  VideoCallManager({
    required this.serverHelper,
    required this.localUser,
    required this.remoteUser,
  }) {
    _log.i('💡 VideoCallManager initialized for ${localUser.username}');
  }

  final _iceServers = {
    'iceServers': [
      {
        'urls': ['stun:stun.l.google.com:19302', 'stun:stun2.l.google.com:19302']
      },
    ]
  };

  Future<void> setupCallEnvironment(ConnectionTarget target) async {
    _log.i('🎬 Setting up call environment for $target');
    RTCPeerConnection? connection = getConnection(target);

    if (connection == null) {
      connection = await createPeerConnection(_iceServers);
      if (target == ConnectionTarget.peer) {
        _peerConnection = connection;
      } else {
        _serverConnection = connection;
      }
      _log.d('🔗 Created new RTCPeerConnection for $target');
    }

    connection.onTrack = (RTCTrackEvent event) {
      _log.d('🌐 onTrack event: stream=${event.streams[0].id}');
      if (event.streams.isNotEmpty) {
        _remoteStreamController.add(event.streams[0]);
      }
    };

    if (_localStream == null) {
      _log.d('📹 Requesting local media stream');
      _localStream = await navigator.mediaDevices.getUserMedia({
        'video': {'facingMode': 'user'},
        'audio': true,
      });
      _localStreamController.add(_localStream!);
      _log.i('📹 Local stream obtained and added to controller');
    }

    _localStream!.getTracks().forEach((track) {
      connection!.addTrack(track, _localStream!);
    });
    _log.d('🔗 Local tracks added to connection for $target');

    _log.i('✅ Call environment setup complete for $target');
  }

  Future<void> negotiateCall(ConnectionTarget target, {bool isCaller = false}) async {
    _log.i('🤝 Negotiating call with target: $target (isCaller=$isCaller)');
    RTCPeerConnection? connection = getConnection(target);
    if (connection == null) {
      _log.e('❌ Cannot negotiate; connection for $target is null');
      return;
    }

    if (isCaller) {
      RTCSessionDescription offer = await createOffer(target);
      _log.d('📣 Created offer: ${offer.sdp}');
      serverHelper.sendMessage(
        msgType: 'offer',
        payload: {
          'from': localUser.userId,
          'target': connection == _peerConnection ? remoteUser!.userId : 'server',
          'other_user': remoteUser!.userId,
          'offer': offer.toMap(),
        },
      );
    } else {
      RTCSessionDescription answer = await createAnswer(target);
      _log.d('📤 Created answer: ${answer.sdp}');
      serverHelper.sendMessage(
        msgType: 'answer',
        payload: {
          'from': localUser.userId,
          'target': connection == _peerConnection ? remoteUser!.userId : 'server',
          'other_user': remoteUser!.userId,
          'answer': answer.toMap(),
        },
      );
    }

    processPendingIceCandidates(target);

    connection.onIceCandidate = (RTCIceCandidate? candidate) {
      if (candidate != null) {
        final candMap = {
          'candidate': candidate.candidate,
          'sdpMid': candidate.sdpMid,
          'sdpMLineIndex': candidate.sdpMLineIndex,
        };
        _log.d('🌐 Sending ICE candidate: $candMap');
        serverHelper.sendMessage(
          msgType: 'ice_candidate',
          payload: {
            'from': localUser.userId,
            'target': connection == _peerConnection ? remoteUser!.userId : 'server',
            'candidate': candMap,
          },
        );
      }
    };

    _log.i('✅ Finished negotiating call for $target');
  }

  Future<RTCSessionDescription> createOffer(ConnectionTarget target) async {
    RTCPeerConnection? connection = getConnection(target);
    RTCSessionDescription offer = await connection!.createOffer();
    await connection.setLocalDescription(offer);
    return offer;
  }

  Future<RTCSessionDescription> createAnswer(ConnectionTarget target) async {
    RTCPeerConnection? connection = getConnection(target);
    RTCSessionDescription answer = await connection!.createAnswer();
    await connection.setLocalDescription(answer);
    return answer;
  }

  Future<void> onReceiveIceCandidate(ConnectionTarget target, Map<String, dynamic> candidateData) async {
    _log.d('🌐 onReceiveIceCandidate for $target: $candidateData');
    RTCPeerConnection? connection = getConnection(target);
    final pending = connection == _peerConnection ? _peerPendingIceCandidates : _serverPendingIceCandidates;
    if (connection == null) {
      _log.d('🗄️ Storing pending ICE candidate for $target');
      pending.add(candidateData);
      return;
    }

    if (candidateData['candidate'] != null) {
      RTCIceCandidate candidate = RTCIceCandidate(
        candidateData['candidate'],
        candidateData['sdpMid'],
        candidateData['sdpMLineIndex'],
      );
      await connection.addCandidate(candidate);
      _log.i('✅ Added ICE candidate for $target: ${candidate.candidate}');
    }
  }

  void processPendingIceCandidates(ConnectionTarget target) {
    _log.d('🔄 Processing pending ICE candidates for $target');
    RTCPeerConnection? connection = getConnection(target);
    if (connection == null) return;
    final pending = connection == _peerConnection ? _peerPendingIceCandidates : _serverPendingIceCandidates;

    for (var candidateData in pending) {
      onReceiveIceCandidate(target, candidateData);
    }
    pending.clear();
    _log.d('✅ Cleared pending ICE candidates for $target');
  }

  Future<void> onReceiveOffer(ConnectionTarget target, Map<String, dynamic> offerData) async {
    _log.i('📥 onReceiveOffer from ${offerData['from']} for $target');
    RTCPeerConnection? connection = getConnection(target);
    if (connection == null) {
      connection = await createPeerConnection(_iceServers);
      if (target == ConnectionTarget.peer) {
        _peerConnection = connection;
      } else {
        _serverConnection = connection;
      }
      _log.d('🔗 Initialized peer connection on offer');
    }
    await connection.setRemoteDescription(
      RTCSessionDescription(offerData['sdp'], offerData['type']),
    );
    negotiateCall(target, isCaller: false);
  }

  Future<void> onReceiveAnswer(ConnectionTarget target, Map<String, dynamic> answerData) async {
    _log.i('📥 onReceiveAnswer for $target');
    RTCPeerConnection? connection = getConnection(target);
    await connection!.setRemoteDescription(
      RTCSessionDescription(answerData['sdp'], answerData['type']),
    );
  }

  void updateRemoteVideoStatus(bool isVideoOn) {
    _log.d('📷 Remote video status changed: $isVideoOn');
    _remoteVideoStatusController.add(isVideoOn);
  }

  RTCPeerConnection? getConnection(ConnectionTarget target) {
    switch (target) {
      case ConnectionTarget.server:
        return _serverConnection;
      case ConnectionTarget.peer:
        return _peerConnection;
    }
  }

  Future<void> flipCamera() async {
    _log.i('🔄 Flipping camera');
    if (_localStream != null) {
      final videoTracks = _localStream!.getVideoTracks();
      if (videoTracks.isNotEmpty) {
        await Helper.switchCamera(videoTracks[0]);
      }
    }
  }

  Future<void> toggleCamera() async {
    _log.i('📷 Toggling camera');
    if (_localStream != null) {
      final videoTracks = _localStream!.getVideoTracks();
      if (videoTracks.isNotEmpty) {
        final track = videoTracks[0];
        track.enabled = !track.enabled;
        _localVideoStatusController.add(track.enabled);
        _log.d('📷 Camera enabled: ${track.enabled}');
      }
    }
  }

  Future<void> toggleMicrophone() async {
    _log.i('🎤 Toggling microphone');
    if (_localStream != null) {
      final audioTracks = _localStream!.getAudioTracks();
      if (audioTracks.isNotEmpty) {
        final track = audioTracks[0];
        track.enabled = !track.enabled;
        _log.d('🎤 Microphone enabled: ${track.enabled}');
      }
    }
  }

  void dispose() {
    _log.i('🗑️ Disposing VideoCallManager resources');
    _localStream?.getTracks().forEach((track) {
      track.stop();
    });
    _localStream?.dispose();
    _localStream = null;

    _localStreamController.close();
    _remoteStreamController.close();
    _localVideoStatusController.close();
    _remoteVideoStatusController.close();

    _peerConnection?.close();
    _peerConnection = null;
    _serverConnection?.close();
    _serverConnection = null;

    _peerPendingIceCandidates.clear();
    _serverPendingIceCandidates.clear();
    _log.i('✅ VideoCallManager disposed');
  }
}
