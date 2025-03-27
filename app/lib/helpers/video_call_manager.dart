// File: video_call_manager.dart
import 'dart:async';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:lip_c/models/lip_c_user.dart';

import '../models/connection_target.dart';
import 'server_helper.dart';

class VideoCallManager {
  RTCPeerConnection? _peerConnection;
  RTCPeerConnection? _serverConnection;
  List<Map<String, dynamic>> _peerPendingIceCandidates = [];
  List<Map<String, dynamic>> _serverPendingIceCandidates = [];

  MediaStream? _localStream;
  final LipCUser localUser;
  LipCUser? remoteUser;
  final ServerHelper serverHelper;

  final _localStreamController = StreamController<MediaStream>.broadcast();
  final StreamController<bool> _localVideoStatusController =
      StreamController<bool>.broadcast();
  final _remoteStreamController = StreamController<MediaStream>.broadcast();
  final StreamController<bool> _remoteVideoStatusController =
      StreamController<bool>.broadcast();

  /// Expose the local media stream.
  Stream<MediaStream> get localStreamStream => _localStreamController.stream;
  Stream<bool> get localVideoStatusStream => _localVideoStatusController.stream;

  /// Expose the remote media stream.
  Stream<MediaStream> get remoteStreamStream => _remoteStreamController.stream;
  Stream<bool> get remoteVideoStatusStream =>
      _remoteVideoStatusController.stream;

  VideoCallManager({
    required this.serverHelper,
    required this.localUser,
    required this.remoteUser,
  });

  final _iceServers = {
    'iceServers': [
      {
        'urls': [
          'stun:stun.l.google.com:19302',
          'stun:stun2.l.google.com:19302'
        ]
      },
      // Optionally add TURN servers here if needed.
    ]
  };

  Future<void> setupCallEnvironment(ConnectionTarget target) async {
    RTCPeerConnection? connection = getConnection(target);
    print("VideoCallManager: Setting up call environment");

    // Create a new RTCPeerConnection if it doesn't exist.
    // ignore: prefer_conditional_assignment
    if (connection == null) {
      connection = await createPeerConnection(_iceServers);

      target == ConnectionTarget.peer
          ? _peerConnection = connection
          : _serverConnection = connection;
    }

    // Set up onTrack listener for remote streams.
    connection.onTrack = (RTCTrackEvent event) {
      print("Received remote stream: ${event.streams[0].id}");
      if (event.streams.isNotEmpty) {
        _remoteStreamController.add(event.streams[0]);
      }
    };

    // Request the local media stream using the front camera.
    // ignore: prefer_conditional_assignment
    if (_localStream == null) {
      _localStream = await navigator.mediaDevices.getUserMedia({
        'video': {'facingMode': 'user'},
        'audio': true,
      });
      // Notify listeners that the local stream is available.
      _localStreamController.add(_localStream!);
    }

    // Add all tracks from the local stream to the peer connection.
    _localStream!.getTracks().forEach((track) {
      connection!.addTrack(track, _localStream!);
    });

    print("Finished setting up call environment for $target");
  }

  Future<void> negotiateCall(ConnectionTarget target,
      {bool isCaller = false}) async {
    RTCPeerConnection? connection = getConnection(target);

    print("Negotiating call with target: $target");
    if (isCaller) {
      RTCSessionDescription offer = await createOffer(target);
      print("Created offer: ${offer.sdp}");
      serverHelper.sendRawMessage({
        "type": "offer",
        "from": localUser.userId,
        "target": connection == _peerConnection ? remoteUser!.userId : 'server',
        "payload": offer.toMap(),
      });
    } else {
      RTCSessionDescription answer = await createAnswer(target);
      print("Created answer to $target | $remoteUser- ${answer.sdp}");
      serverHelper.sendRawMessage({
        "type": "answer",
        "from": localUser.userId,
        "target": connection == _peerConnection ? remoteUser!.userId : 'server',
        "payload": answer.toMap(),
      });
    }

    // Process any pending ICE candidates.
    processPendingIceCandidates(target);

    // Send generated ICE candidates to the remote user.
    connection!.onIceCandidate = (RTCIceCandidate? candidate) {
      if (candidate != null) {
        print("Sending candidate: ${{
          'candidate': candidate.candidate,
          'sdpMid': candidate.sdpMid,
          'sdpMLineIndex': candidate.sdpMLineIndex,
        }}");

        serverHelper.sendRawMessage({
          'type': 'ice_candidate',
          'from': localUser.userId,
          'target':
              connection == _peerConnection ? remoteUser!.userId : 'server',
          'payload': {
            'candidate': candidate.candidate,
            'sdpMid': candidate.sdpMid,
            'sdpMLineIndex': candidate.sdpMLineIndex,
          }
        });
      }
    };

    print("Finished negotiating call");
  }

  /// Create an SDP offer.
  Future<RTCSessionDescription> createOffer(ConnectionTarget target) async {
    RTCPeerConnection? connection = getConnection(target);
    RTCSessionDescription offer = await connection!.createOffer();
    await connection.setLocalDescription(offer);
    return offer;
  }

  /// Create an SDP answer.
  Future<RTCSessionDescription> createAnswer(ConnectionTarget target) async {
    RTCPeerConnection? connection = getConnection(target);
    RTCSessionDescription answer = await connection!.createAnswer();
    await connection.setLocalDescription(answer);
    return answer;
  }

  Future<void> onReceiveIceCandidate(
      ConnectionTarget target, Map<String, dynamic> candidateData) async {
    RTCPeerConnection? connection = getConnection(target);
    List<Map<String, dynamic>> pendingCandidates = connection == _peerConnection
        ? _peerPendingIceCandidates
        : _serverPendingIceCandidates;

    // If the peer connection isn't ready, store the candidate and return.
    if (connection == null) {
      print(
          "ICE candidate received, but _peerConnection is null. Storing candidate.");
      pendingCandidates.add(candidateData);
      return;
    }

    // Process the incoming candidate.
    if (candidateData['candidate'] != null) {
      RTCIceCandidate candidate = RTCIceCandidate(
        candidateData['candidate'],
        candidateData['sdpMid'],
        candidateData['sdpMLineIndex'],
      );
      await connection.addCandidate(candidate);
      print("Added ICE candidate: ${candidate.candidate}");
    }
  }

// Call this method after the peer connection has been created and initialized.
  void processPendingIceCandidates(ConnectionTarget target) {
    RTCPeerConnection? connection = getConnection(target);
    if (connection == null) {
      return;
    }

    List<Map<String, dynamic>> pendingCandidates = connection == _peerConnection
        ? _peerPendingIceCandidates
        : _serverPendingIceCandidates;

    if (pendingCandidates.isNotEmpty) {
      for (var candidateData in pendingCandidates) {
        onReceiveIceCandidate(target, candidateData);
      }
      pendingCandidates.clear();
    }
  }

  Future<void> onReceiveOffer(
      ConnectionTarget target, Map<String, dynamic> offerData) async {
    RTCPeerConnection? connection = getConnection(target);
    // ignore: prefer_conditional_assignment
    if (connection == null) {
      connection = await createPeerConnection(
          _iceServers); // Ensure peer connection is initialized

      target == ConnectionTarget.peer
          ? _peerConnection = connection
          : _serverConnection = connection;
    }

    await connection.setRemoteDescription(
        RTCSessionDescription(offerData['sdp'], offerData['type']));

    negotiateCall(target, isCaller: false);
  }

  Future<void> onReceiveAnswer(
      ConnectionTarget target, Map<String, dynamic> answerData) async {
    RTCPeerConnection? connection = getConnection(target);
    await connection!.setRemoteDescription(
        RTCSessionDescription(answerData['sdp'], answerData['type']));
  }

  void updateRemoteVideoStatus(bool isVideoOn) {
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

  // Flip the camera on the local media stream.
  Future<void> flipCamera() async {
    if (_localStream != null) {
      final videoTracks = _localStream!.getVideoTracks();
      if (videoTracks.isNotEmpty) {
        await Helper.switchCamera(videoTracks[0]);
      }
    }
  }

  // Toggle the camera on the local media stream.
  Future<void> toggleCamera() async {
    if (_localStream != null) {
      final videoTracks = _localStream!.getVideoTracks();
      if (videoTracks.isNotEmpty) {
        final track = videoTracks[0];
        track.enabled = !track.enabled;
      }
    }
  }

  // Toggle the microphone on the local media stream.
  Future<void> toggleMicrophone() async {
    if (_localStream != null) {
      final audioTracks = _localStream!.getAudioTracks();
      if (audioTracks.isNotEmpty) {
        final track = audioTracks[0];
        track.enabled = !track.enabled;
      }
    }
  }

  void setRemoteUser(LipCUser remoteUser) {
    this.remoteUser = remoteUser;
  }

  // Dispose of the resources.
  void dispose() {
    _localStream?.dispose();
    _peerConnection?.close();
    _serverConnection?.close();
    _localStreamController.close();
    _localVideoStatusController.close();
    _remoteStreamController.close();
    _remoteVideoStatusController.close();
  }
}
