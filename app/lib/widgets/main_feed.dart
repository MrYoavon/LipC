import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

class MainFeed extends StatelessWidget {
  final RTCVideoRenderer remoteRenderer;
  final bool isRemoteCameraOn;
  final Widget placeholder; // Widget to show when video is off

  const MainFeed({
    super.key,
    required this.remoteRenderer,
    required this.isRemoteCameraOn,
    required this.placeholder,
  });

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: isRemoteCameraOn
          ? RTCVideoView(
              remoteRenderer,
              objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
            )
          : placeholder,
    );
  }
}
