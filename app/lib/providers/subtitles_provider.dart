// lib/providers/subtitles_provider.dart

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../helpers/app_logger.dart';

class SubtitlesNotifier extends StateNotifier<String> {
  final Logger _log = AppLogger.instance;

  SubtitlesNotifier() : super("Live subtitles will appear here.") {
    _log.i('💬 SubtitlesNotifier initialized with: "$state"');
  }

  /// Updates the subtitle text.
  void update(String newSubtitles) {
    _log.d('💬 Updating subtitles: "$newSubtitles"');
    state = newSubtitles;
  }
}

final subtitlesProvider = StateNotifierProvider<SubtitlesNotifier, String>(
  (ref) => SubtitlesNotifier(),
);
