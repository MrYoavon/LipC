import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';

class CallControls extends StatefulWidget {
  final VoidCallback onFlipCamera;
  final VoidCallback onToggleCamera;
  final VoidCallback onEndCall;
  final VoidCallback onToggleMute;

  const CallControls({
    super.key,
    required this.onFlipCamera,
    required this.onToggleCamera,
    required this.onToggleMute,
    required this.onEndCall,
  });

  @override
  State<CallControls> createState() => _CallControlsState();
}

class _CallControlsState extends State<CallControls> {
  bool isCameraOn = true;

  bool isMuted = false;

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
              onPressed: () {
                widget.onFlipCamera();
              },
            ),
          ),
          // Mute/Unmute
          CircleAvatar(
            radius: 28,
            backgroundColor: isMuted ? Colors.grey.shade800 : Colors.white,
            child: IconButton(
              icon: isMuted
                  ? const Icon(LucideIcons.micOff, color: Colors.white)
                  : Icon(LucideIcons.mic, color: Colors.grey.shade800),
              onPressed: () {
                isMuted = !isMuted;
                widget.onToggleMute();
              },
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
              onPressed: () {
                isCameraOn = !isCameraOn;
                widget.onToggleCamera();
              },
            ),
          ),
          // End Call
          CircleAvatar(
            radius: 28,
            backgroundColor: Colors.red,
            child: IconButton(
              icon: const Icon(LucideIcons.phoneOff, color: Colors.white),
              onPressed: () {
                widget.onEndCall();
              },
            ),
          ),
        ],
      ),
    );
  }
}
