import 'package:flutter/services.dart';

class NV21Converter {
  static const _channel = MethodChannel('com.example.lip_c/yuv');

  /// Converts NV21 image data to a PNG-encoded RGB image.
  ///
  /// [nv21Data] - Raw NV21 data.
  /// [width] and [height] - Dimensions of the image.
  ///
  /// Returns a [Uint8List] containing the PNG data.
  static Future<Uint8List> convertNV21ToRGB(
      Uint8List nv21Data, int width, int height) async {
    final result = await _channel.invokeMethod<Uint8List>(
      'convertNV21ToRGB',
      {
        'data': nv21Data,
        'width': width,
        'height': height,
      },
    );
    if (result == null) {
      throw Exception('NV21 to RGB conversion returned null.');
    }
    return result;
  }
}
