import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

class MainFeed extends StatelessWidget {
  final RTCVideoRenderer remoteRenderer;

  const MainFeed({
    super.key,
    required this.remoteRenderer,
  });

  @override
  Widget build(BuildContext context) {
    print("BBBBBBBBBBBBBBBBBBBBBBBBBB$remoteRenderer");
    return Positioned.fill(
      child: RTCVideoView(
        remoteRenderer,
        objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
      ),
    );
  }
}
