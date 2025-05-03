import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:lip_c/models/lip_c_user.dart';
import 'package:lip_c/widgets/server_connection_indicator.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../helpers/server_helper.dart';
import '../helpers/video_call_manager.dart';
import '../widgets/call_controls.dart';
import '../widgets/main_feed.dart';
import '../widgets/pip_preview.dart';
import '../widgets/subtitles_display.dart';

class CallPage extends StatefulWidget {
  final LipCUser localUser;
  final LipCUser remoteUser;
  final ServerHelper serverHelper;
  final VideoCallManager videoCallManager;

  const CallPage({
    super.key,
    required this.localUser,
    required this.remoteUser,
    required this.serverHelper,
    required this.videoCallManager,
  });

  @override
  State<CallPage> createState() => _CallPageState();
}

class _CallPageState extends State<CallPage> {
  final Logger _log = AppLogger.instance;

  // Renderers for displaying video streams.
  final RTCVideoRenderer _localRenderer = RTCVideoRenderer();
  final RTCVideoRenderer _remoteRenderer = RTCVideoRenderer();
  bool isRemoteCameraOn = true;

  bool isCallInitialized = false;

  @override
  void initState() {
    super.initState();
    _log.i('💡 CallPage mounted');
    _initRenderers();
    _initCall();
  }

  // Initialize the RTCVideoRenderers.
  Future<void> _initRenderers() async {
    _log.d('🎥 Initializing video renderers');
    await _localRenderer.initialize();
    await _remoteRenderer.initialize();
    _log.d('🎥 Video renderers initialized');
  }

  // Initialize the WebRTC call: capture local media, set up connection, and handle remote stream.
  Future<void> _initCall() async {
    _log.i('📞 Initializing call between ${widget.localUser.username} and ${widget.remoteUser.username}');

    // Subscribe to the remote stream.
    widget.videoCallManager.remoteStreamStream.listen((stream) {
      _log.d('🌐 Received remote stream');
      setState(() {
        _remoteRenderer.srcObject = stream;
      });
    });

    // Subscribe to the local stream.
    widget.videoCallManager.localStreamStream.listen((stream) {
      _log.d('🖥️ Received local stream');
      setState(() {
        _localRenderer.srcObject = stream;
      });
    });

    // Listen to remote video status updates.
    widget.videoCallManager.remoteVideoStatusStream.listen((isVideoOn) {
      _log.d('📷 Remote video status: ${isVideoOn ? "ON" : "OFF"}');
      setState(() {
        isRemoteCameraOn = isVideoOn;
      });
    });

    setState(() {
      isCallInitialized = true;
    });
    _log.i('✅ Call initialized');
  }

  Widget _buildRemotePlaceholder() {
    // Check if the remote user has a profile picture.
    if (widget.remoteUser.profilePic.isNotEmpty) {
      return CircleAvatar(
        radius: 50,
        backgroundImage: NetworkImage(widget.remoteUser.profilePic),
        backgroundColor: Colors.transparent,
      );
    } else {
      // Build initials from the remote user's name.
      String initials =
          widget.remoteUser.name.split(' ').where((e) => e.isNotEmpty).map((e) => e[0]).take(2).join().toUpperCase();
      return CircleAvatar(
        radius: 50,
        backgroundColor: Colors.blue,
        child: Text(
          initials,
          style: const TextStyle(fontSize: 24, color: Colors.white),
        ),
      );
    }
  }

  @override
  void dispose() {
    _log.i('🗑️ CallPage disposed - cleaning up');
    _localRenderer.srcObject = null;
    _localRenderer.dispose();
    _remoteRenderer.srcObject = null;
    _remoteRenderer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ServerConnectionIndicator(
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(
          children: [
            // Main Feed: Full-screen remote video or placeholder.
            MainFeed(
              remoteRenderer: _remoteRenderer,
              isRemoteCameraOn: isRemoteCameraOn,
              placeholder: _buildRemotePlaceholder(),
            ),

            // Picture-in-Picture preview.
            PipPreview(localRenderer: _localRenderer),

            // Subtitles overlay.
            SubtitlesDisplay(),

            // Call Controls.
            CallControls(
              onFlipCamera: () {
                _log.i('🔄 Flipping local camera');
                widget.videoCallManager.flipCamera();
                setState(() {});
              },
              onToggleCamera: () {
                _log.i('📷 Toggling local camera');
                widget.videoCallManager.toggleCamera();
                setState(() {});
              },
              onToggleMute: () {
                _log.i('🎤 Toggling microphone mute');
                widget.videoCallManager.toggleMicrophone();
                setState(() {});
              },
              onEndCall: () {
                _log.i('✂️ Ending call, sending hang-up');
                widget.serverHelper.sendMessage(
                  msgType: "call_end",
                  payload: {
                    "from": widget.localUser.userId,
                    "target": widget.remoteUser.userId,
                  },
                );
                widget.videoCallManager.dispose();
                Navigator.pop(context);
                _log.i('🏁 CallPage popped');
              },
            ),
          ],
        ),
      ),
    );
  }
}
