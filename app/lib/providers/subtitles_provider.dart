import 'package:flutter_riverpod/flutter_riverpod.dart';

class SubtitlesNotifier extends StateNotifier<String> {
  // The initial state can be an empty string or some default text.
  SubtitlesNotifier() : super("Live subtitles will appear here.");

  // This method updates the subtitle text.
  void update(String newSubtitles) {
    state = newSubtitles;
  }
}

final subtitlesProvider = StateNotifierProvider<SubtitlesNotifier, String>(
  (ref) => SubtitlesNotifier(),
);
