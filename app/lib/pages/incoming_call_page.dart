// lib/pages/incoming_call_page.dart

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_ringtone_player/flutter_ringtone_player.dart';
import 'package:vibration/vibration.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';
import '../models/lip_c_user.dart';
import '../constants.dart';

class IncomingCallPage extends StatefulWidget {
  final LipCUser remoteUser;
  final VoidCallback onReject;
  final VoidCallback onAccept;

  const IncomingCallPage({
    super.key,
    required this.remoteUser,
    required this.onReject,
    required this.onAccept,
  });

  @override
  State<IncomingCallPage> createState() => _IncomingCallPageState();
}

class _IncomingCallPageState extends State<IncomingCallPage> {
  final Logger _log = AppLogger.instance;
  Timer? _stopRingtoneTimer;

  @override
  void initState() {
    super.initState();
    _log.i('💡 IncomingCallPage mounted for ${widget.remoteUser.username}');
    _startVibration();
    _startRingtone();
  }

  void _startVibration() async {
    if (await Vibration.hasVibrator()) {
      _log.d('🔔 Starting vibration pattern');
      Vibration.vibrate(pattern: [0, 1000, 500, 1000], repeat: 0);
    } else {
      _log.w('⚠️ Device has no vibrator');
    }
  }

  void _startRingtone() {
    _log.d('🎶 Playing ringtone');
    FlutterRingtonePlayer().play(
      fromAsset: 'assets/audio/hey_now_ringtone.mp3',
      looping: true,
      volume: 1.0,
      asAlarm: true,
    );
    _stopRingtoneTimer = Timer(const Duration(seconds: 30), () {
      _log.d('⏰ Stopping ringtone after timeout');
      FlutterRingtonePlayer().stop();
    });
  }

  @override
  void dispose() {
    _log.i('🗑️ IncomingCallPage disposed, stopping alerts');
    _stopRingtoneTimer?.cancel();
    FlutterRingtonePlayer().stop();
    Vibration.cancel();
    super.dispose();
  }

  Widget _buildProfileAvatar() {
    String initials =
        widget.remoteUser.name.split(" ").map((e) => e.isNotEmpty ? e[0].toUpperCase() : '').take(2).join();
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

  void _handleReject() {
    _log.i('❌ Incoming call from ${widget.remoteUser.username} rejected');
    FlutterRingtonePlayer().stop();
    Vibration.cancel();
    widget.onReject();
  }

  void _handleAccept() {
    _log.i('✅ Incoming call from ${widget.remoteUser.username} accepted');
    FlutterRingtonePlayer().stop();
    Vibration.cancel();
    widget.onAccept();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      child: Scaffold(
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
                        onPressed: _handleReject,
                        icon: const Icon(Icons.call_end),
                        color: Colors.red,
                        iconSize: 60,
                      ),
                      IconButton(
                        onPressed: _handleAccept,
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
