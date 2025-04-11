import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:lip_c/models/lip_c_user.dart';
import 'package:lip_c/widgets/server_connection_indicator.dart';
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
  // Renderers for displaying video streams.
  final RTCVideoRenderer _localRenderer = RTCVideoRenderer();
  final RTCVideoRenderer _remoteRenderer = RTCVideoRenderer();
  bool isRemoteCameraOn = true;

  String subtitles = "Live subtitles will appear here.";
  bool isCallInitialized = false;

  @override
  void initState() {
    super.initState();
    _initRenderers();
    _initCall();
  }

  // Initialize the RTCVideoRenderers.
  Future<void> _initRenderers() async {
    await _localRenderer.initialize();
    await _remoteRenderer.initialize();
  }

  // Initialize the WebRTC call: capture local media, set up connection, and handle remote stream.
  Future<void> _initCall() async {
    print("CallPage: Initializing call");

    // Subscribe to the remote stream.
    widget.videoCallManager.remoteStreamStream.listen((stream) {
      setState(() {
        _remoteRenderer.srcObject = stream;
      });
    });

    // Subscribe to the local stream.
    widget.videoCallManager.localStreamStream.listen((stream) {
      setState(() {
        _localRenderer.srcObject = stream;
      });
    });

    // Listen to remote video status updates.
    widget.videoCallManager.remoteVideoStatusStream.listen((isVideoOn) {
      setState(() {
        // Update a local state variable to conditionally display the video stream or profile image.
        isRemoteCameraOn = isVideoOn;
      });
    });

    setState(() {
      isCallInitialized = true;
    });
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
      String initials = widget.remoteUser.name
          .split(' ')
          .map((e) => e.isNotEmpty ? e[0] : '')
          .take(2)
          .join();
      return CircleAvatar(
        radius: 50,
        backgroundColor: Colors.blue,
        child: Text(
          initials,
          style: TextStyle(fontSize: 24, color: Colors.white),
        ),
      );
    }
  }

  @override
  void dispose() {
    // Dispose of the renderers to free up resources.
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
            // Main Feed: Full-screen image view.
            MainFeed(
              remoteRenderer: _remoteRenderer,
              isRemoteCameraOn: isRemoteCameraOn,
              placeholder: _buildRemotePlaceholder(),
            ),
            // Picture-in-Picture preview.
            PipPreview(localRenderer: _localRenderer),
            // Subtitles overlay.
            SubtitlesDisplay(subtitles: subtitles),
            // Call Controls.
            CallControls(
              onFlipCamera: () {
                widget.videoCallManager.flipCamera();
                setState(() {});
              },
              onToggleCamera: () {
                widget.videoCallManager.toggleCamera();
                setState(() {});
              },
              onEndCall: () {
                // 1. Send call end message to the server.
                widget.videoCallManager.remoteUser?.userId != null
                    ? widget.serverHelper.sendEncryptedMessage({
                        "type": "call_end",
                        "from": widget.localUser.userId,
                        "target": widget.remoteUser.userId,
                      })
                    : null;

                // 2. End the call.
                widget.videoCallManager.dispose();

                // 3. Pop the call page
                Navigator.pop(context);
              },
              onToggleMute: () {
                widget.videoCallManager.toggleMicrophone();
                setState(() {});
              },
            ),
          ],
        ),
      ),
    );
  }
}
