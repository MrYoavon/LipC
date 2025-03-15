import 'package:flutter/material.dart';

class AppColors {
  static const Color primary = Color(0xFF0A0E21);
  static const Color accent = Color.fromARGB(255, 65, 115, 221);
  static const Color background = Color(0xFFFFFFFF);
  static const Color textPrimary = Color(0xFF111328);
  static const Color textSecondary = Color(0xFF747474);
  static const List<Color> contactColors = [
    Colors.red,
    Colors.blue,
    Colors.green,
    Colors.orange,
    Colors.purple,
    Colors.teal,
    Colors.amber,
    Colors.indigo,
  ];

  Color getUserColor(String userId) {
    final index = userId.hashCode.abs() % contactColors.length;
    return contactColors[index];
  }

  // Add more color definitions as needed
}

class AppConstants {
  static const double defaultPadding = 16.0;
  static const double defaultMargin = 16.0;
  // Add other constants such as font sizes, durations, etc.
}
