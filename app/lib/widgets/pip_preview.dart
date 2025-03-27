import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';

class PipPreview extends StatelessWidget {
  final RTCVideoRenderer localRenderer;
  const PipPreview({
    super.key,
    required this.localRenderer,
  });

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: 40,
      right: 20,
      width: 120,
      height: 160,
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: Colors.white, width: 2),
        ),
        child: RTCVideoView(
          localRenderer,
          mirror: true,
          objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
        ),
      ),
    );
  }
}
