import 'package:flutter/material.dart';
import '../constants.dart';

/// A simple splash screen that displays the logo in the center
/// and continuously spins it around its center.
class SplashScreen extends StatefulWidget {
  const SplashScreen({Key? key}) : super(key: key);

  @override
  _SplashScreenState createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    // Rotate once every 2 seconds
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: RotationTransition(
          turns: _controller,
          child: Image.asset(
            'assets/logo.png',
            width: 120,
            height: 120,
            color: AppColors.accent,
          ),
        ),
      ),
    );
  }
}
