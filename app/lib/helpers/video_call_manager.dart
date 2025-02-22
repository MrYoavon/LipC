// File: video_call_manager.dart
import 'dart:async';
import 'package:flutter_webrtc/flutter_webrtc.dart';

import 'server_helper.dart';

class VideoCallManager {
  RTCPeerConnection? _peerConnection;
  List<Map<String, dynamic>> _pendingIceCandidates = [];
  MediaStream? _localStream;
  final ServerHelper serverHelper;
  final String localUsername;
  String remoteUsername;

  final _localStreamController = StreamController<MediaStream>.broadcast();
  final _remoteStreamController = StreamController<MediaStream>.broadcast();

  /// Expose the local media stream.
  Stream<MediaStream> get localStreamStream => _localStreamController.stream;

  /// Expose the remote media stream.
  Stream<MediaStream> get remoteStreamStream => _remoteStreamController.stream;

  VideoCallManager({
    required this.serverHelper,
    required this.localUsername,
    required this.remoteUsername,
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

  Future<void> setupCallEnvironment() async {
    print("VideoCallManager: Setting up call environment");

    // Create a new RTCPeerConnection if it doesn't exist.
    // ignore: prefer_conditional_assignment
    if (_peerConnection == null) {
      _peerConnection = await createPeerConnection(_iceServers);
    }

    // Process any pending ICE candidates.
    processPendingIceCandidates();

    // Send generated ICE candidates to the remote user.
    _peerConnection!.onIceCandidate = (RTCIceCandidate? candidate) {
      if (candidate != null) {
        print("Sending candidate: ${{
          'candidate': candidate.candidate,
          'sdpMid': candidate.sdpMid,
          'sdpMLineIndex': candidate.sdpMLineIndex,
        }}");

        serverHelper.sendRawMessage({
          'type': 'ice_candidate',
          'from': localUsername,
          'target': remoteUsername,
          'payload': {
            'candidate': candidate.candidate,
            'sdpMid': candidate.sdpMid,
            'sdpMLineIndex': candidate.sdpMLineIndex,
          }
        });
      }
    };

    // Set up onTrack listener for remote streams.
    _peerConnection!.onTrack = (RTCTrackEvent event) {
      if (event.streams.isNotEmpty) {
        _remoteStreamController.add(event.streams[0]);
      }
    };

    // Request the local media stream using the front camera.
    _localStream = await navigator.mediaDevices.getUserMedia({
      'video': {'facingMode': 'user'},
      'audio': true,
    });

    // Add all tracks from the local stream to the peer connection.
    _localStream!.getTracks().forEach((track) {
      _peerConnection!.addTrack(track, _localStream!);
    });

    // Notify listeners that the local stream is available.
    _localStreamController.add(_localStream!);

    print("Finished setting up call environment");
  }

  Future<void> negotiateCall({bool isCaller = false}) async {
    print("Negotiating call");
    if (isCaller) {
      RTCSessionDescription offer = await createOffer();
      serverHelper.sendRawMessage({
        "type": "offer",
        "from": localUsername,
        "target": remoteUsername,
        "payload": offer.toMap(),
      });
    } else {
      RTCSessionDescription answer = await createAnswer();
      serverHelper.sendRawMessage({
        "type": "answer",
        "from": localUsername,
        "target": remoteUsername,
        "payload": answer.toMap(),
      });
    }
    print("Finished negotiating call");
  }

  /// Create an SDP offer.
  Future<RTCSessionDescription> createOffer() async {
    RTCSessionDescription offer = await _peerConnection!.createOffer();
    await _peerConnection!.setLocalDescription(offer);
    return offer;
  }

  /// Create an SDP answer.
  Future<RTCSessionDescription> createAnswer() async {
    RTCSessionDescription answer = await _peerConnection!.createAnswer();
    await _peerConnection!.setLocalDescription(answer);
    return answer;
  }

  Future<void> onReceiveIceCandidate(Map<String, dynamic> candidateData) async {
    // If the peer connection isn't ready, store the candidate and return.
    if (_peerConnection == null) {
      print(
          "ICE candidate received, but _peerConnection is null. Storing candidate.");
      _pendingIceCandidates.add(candidateData);
      return;
    }

    // Process the incoming candidate.
    if (candidateData['candidate'] != null) {
      RTCIceCandidate candidate = RTCIceCandidate(
        candidateData['candidate'],
        candidateData['sdpMid'],
        candidateData['sdpMLineIndex'],
      );
      await _peerConnection!.addCandidate(candidate);
      print("Added ICE candidate: ${candidate.candidate}");
    }
  }

// Call this method after the peer connection has been created and initialized.
  void processPendingIceCandidates() {
    if (_peerConnection != null && _pendingIceCandidates.isNotEmpty) {
      for (var candidateData in _pendingIceCandidates) {
        onReceiveIceCandidate(candidateData);
      }
      _pendingIceCandidates.clear();
    }
  }

  Future<void> onReceiveOffer(Map<String, dynamic> offerData) async {
    // ignore: prefer_conditional_assignment
    if (_peerConnection == null) {
      _peerConnection = await createPeerConnection(
          _iceServers); // Ensure peer connection is initialized
    }

    await _peerConnection!.setRemoteDescription(
        RTCSessionDescription(offerData['sdp'], offerData['type']));

    negotiateCall(isCaller: false);
  }

  Future<void> onReceiveAnswer(Map<String, dynamic> answerData) async {
    await _peerConnection!.setRemoteDescription(
        RTCSessionDescription(answerData['sdp'], answerData['type']));
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

  // Dispose of the resources.
  void dispose() {
    _localStream?.dispose();
    _peerConnection?.close();
    _localStreamController.close();
    _remoteStreamController.close();
  }
}
