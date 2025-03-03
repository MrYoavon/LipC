import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import '../helpers/server_helper.dart';
import '../helpers/video_call_manager.dart';
import '../widgets/call_controls.dart';
import '../widgets/main_feed.dart';
import '../widgets/pip_preview.dart';
import '../widgets/subtitles_display.dart';

class CallPage extends StatefulWidget {
  final String localUsername;
  final String remoteUsername; // The username of the remote peer.
  final ServerHelper serverHelper;
  final VideoCallManager videoCallManager;

  const CallPage({
    super.key,
    required this.localUsername,
    required this.remoteUsername,
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
      print("CallPage: Received remote stream");
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

    setState(() {
      isCallInitialized = true;
    });
  }

  @override
  void dispose() {
    _localRenderer.dispose();
    _remoteRenderer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Main Feed: Full-screen image view.
          MainFeed(remoteRenderer: _remoteRenderer),
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
              Navigator.pop(context);
            },
            onToggleMute: () {
              widget.videoCallManager.toggleMicrophone();
              setState(() {});
            },
          ),
        ],
      ),
    );
  }
}
