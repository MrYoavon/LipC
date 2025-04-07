import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_ringtone_player/flutter_ringtone_player.dart';
import 'package:vibration/vibration.dart';

import '../models/lip_c_user.dart';
import '../constants.dart';

class IncomingCallPage extends StatefulWidget {
  final LipCUser remoteUser;
  final Map<String, dynamic> callData;
  final VoidCallback onReject;
  final VoidCallback onAccept;

  const IncomingCallPage({
    super.key,
    required this.remoteUser,
    required this.callData,
    required this.onReject,
    required this.onAccept,
  });

  @override
  State<IncomingCallPage> createState() => _IncomingCallPageState();
}

class _IncomingCallPageState extends State<IncomingCallPage> {
  Timer? _stopRingtoneTimer;

  @override
  void initState() {
    super.initState();
    _startVibration();
    _startRingtone();
  }

  void _startVibration() async {
    if (await Vibration.hasVibrator()) {
      // Pattern: wait 0ms, vibrate for 1000ms, pause for 500ms, then vibrate for 1000ms
      Vibration.vibrate(pattern: [0, 1000, 500, 1000], repeat: 0);
    }
  }

  void _startRingtone() {
    FlutterRingtonePlayer().play(
      fromAsset: 'assets/audio/hey_now_ringtone.mp3',
      looping: true,
      volume: 1.0,
      asAlarm: true,
    );
    // Stop the ringtone after 30 seconds.
    _stopRingtoneTimer = Timer(const Duration(seconds: 30), () {
      FlutterRingtonePlayer().stop();
    });
  }

  @override
  void dispose() {
    _stopRingtoneTimer?.cancel();
    FlutterRingtonePlayer().stop();
    Vibration.cancel();
    super.dispose();
  }

  Widget _buildProfileAvatar() {
    if (widget.remoteUser.profilePic.isNotEmpty) {
      return CircleAvatar(
        radius: 80,
        backgroundImage: NetworkImage(widget.remoteUser.profilePic),
        backgroundColor: Colors.transparent,
      );
    } else {
      // Generate initials from the user's name.
      String initials = widget.remoteUser.name
          .split(" ")
          .map((e) => e.isNotEmpty ? e[0].toUpperCase() : '')
          .take(2)
          .join();
      return CircleAvatar(
        radius: 80,
        backgroundColor: AppColors().getUserColor(widget.remoteUser.userId),
        child: Text(
          initials,
          style: const TextStyle(
            fontSize: 40,
            color: AppColors.background,
            fontWeight: FontWeight.bold,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop:
          false, // Prevents the user from going back to the previous screen yet allows us to use Navigator.pop(context).
      child: Scaffold(
        // No AppBar to remove the back arrow.
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [
                Color.fromARGB(255, 55, 159, 243),
                Color.fromARGB(255, 142, 181, 240),
              ],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
          child: SafeArea(
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildProfileAvatar(),
                  const SizedBox(height: 20),
                  Text(
                    widget.remoteUser.name,
                    style: const TextStyle(
                      fontSize: 30,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '@${widget.remoteUser.username}',
                    style: const TextStyle(
                      fontSize: 20,
                      color: Colors.white70,
                    ),
                  ),
                  const SizedBox(height: 50),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      IconButton(
                        onPressed: () {
                          FlutterRingtonePlayer().stop();
                          Vibration.cancel();
                          widget.onReject();
                        },
                        icon: const Icon(Icons.call_end),
                        color: Colors.red,
                        iconSize: 60,
                      ),
                      IconButton(
                        onPressed: () {
                          FlutterRingtonePlayer().stop();
                          Vibration.cancel();
                          widget.onAccept();
                        },
                        icon: const Icon(Icons.call),
                        color: Colors.green,
                        iconSize: 60,
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Incoming Call',
                    style: TextStyle(
                      fontSize: 18,
                      color: Colors.white70,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
