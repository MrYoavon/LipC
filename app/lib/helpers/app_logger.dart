import 'package:logger/logger.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';

class AppLogger {
  static late Logger _logger;

  static Future<void> init() async {
    final dir = await getApplicationDocumentsDirectory();
    final logFile = File('${dir.path}/app.log');

    // File output
    var fileOutput = FileOutput(file: logFile);

    // Console + file
    _logger = Logger(
      printer: PrettyPrinter(), // human-friendly format
      output: MultiOutput([
        // combine outputs
        ConsoleOutput(),
        fileOutput,
      ]),
    );
  }

  static Logger get instance => _logger;
}
