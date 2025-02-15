import 'package:flutter/material.dart';

class SubtitlesDisplay extends StatelessWidget {
  final String subtitles;
  const SubtitlesDisplay({
    Key? key,
    required this.subtitles,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Positioned(
      bottom: 110,
      left: 20,
      right: 20,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 15),
        decoration: BoxDecoration(
          color: Colors.black.withAlpha(153),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          subtitles,
          style: const TextStyle(color: Colors.white, fontSize: 16),
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
