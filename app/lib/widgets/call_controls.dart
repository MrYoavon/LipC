import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';

class CallControls extends StatelessWidget {
  final VoidCallback onFlipCamera;
  final VoidCallback onToggleCamera;
  final VoidCallback onEndCall;
  final bool isCameraOn;
  const CallControls({
    Key? key,
    required this.onFlipCamera,
    required this.onToggleCamera,
    required this.onEndCall,
    required this.isCameraOn,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Positioned(
      bottom: 30,
      left: 20,
      right: 20,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          // Flip Camera
          CircleAvatar(
            radius: 28,
            backgroundColor: Colors.grey.shade800,
            child: IconButton(
              icon: const Icon(LucideIcons.refreshCw, color: Colors.white),
              onPressed: onFlipCamera,
            ),
          ),
          // Mute/Unmute (dummy)
          CircleAvatar(
            radius: 28,
            backgroundColor: Colors.grey.shade800,
            child: IconButton(
              icon: const Icon(LucideIcons.mic, color: Colors.white),
              onPressed: () {},
            ),
          ),
          // Toggle Video
          CircleAvatar(
            radius: 28,
            backgroundColor: isCameraOn ? Colors.white : Colors.grey.shade800,
            child: IconButton(
              icon: isCameraOn
                  ? Icon(LucideIcons.video, color: Colors.grey.shade800)
                  : const Icon(LucideIcons.videoOff, color: Colors.white),
              onPressed: onToggleCamera,
            ),
          ),
          // End Call
          CircleAvatar(
            radius: 28,
            backgroundColor: Colors.red,
            child: IconButton(
              icon: const Icon(LucideIcons.phoneOff, color: Colors.white),
              onPressed: onEndCall,
            ),
          ),
        ],
      ),
    );
  }
}
