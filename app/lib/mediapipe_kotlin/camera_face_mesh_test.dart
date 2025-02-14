import 'dart:async';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image/image.dart' as imglib;

class CallPage extends StatefulWidget {
  final String username;
  const CallPage({Key? key, required this.username}) : super(key: key);

  @override
  State<CallPage> createState() => _CallPageState();
}

class _CallPageState extends State<CallPage> {
  static const MethodChannel _methodChannel =
      MethodChannel('com.example.lip_c/face_mesh');
  static const EventChannel _eventChannel =
      EventChannel('com.example.lip_c/face_mesh/events');

  CameraController? _cameraController;
  List<CameraDescription>? cameras;
  Uint8List? _processedImageBytes;
  StreamSubscription? _eventSubscription;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _startFaceMesh();
  }

  Future<void> _initializeCamera() async {
    cameras = await availableCameras();
    final frontCamera = cameras!.firstWhere(
      (camera) => camera.lensDirection == CameraLensDirection.front,
    );
    _cameraController = CameraController(
      frontCamera,
      ResolutionPreset.medium,
      imageFormatGroup: ImageFormatGroup.yuv420,
      fps: 5,
    );
    await _cameraController!.initialize();
    _cameraController!.startImageStream(_onLatestImage);
  }

  void _onLatestImage(CameraImage image) async {
    try {
      final jpegBytes = await convertYUV420toJPEG(image);
      if (jpegBytes.isNotEmpty) {
        await _methodChannel.invokeMethod('sendFrame', jpegBytes);
      }
    } catch (e) {
      debugPrint('Error processing camera image: $e');
    }
  }

  // Convert YUV420 image from CameraImage to JPEG bytes using the image package.
  Future<Uint8List> convertYUV420toJPEG(CameraImage image) async {
    final int width = image.width;
    final int height = image.height;

    // Use the plane width if available; otherwise, assume half the image width.
    final int uvWidth = image.planes[1].width ?? (width ~/ 2);
    final int uvRowStride = image.planes[1].bytesPerRow;
    // Calculate the pixel stride as bytesPerRow divided by the width of the UV plane.
    final int uvPixelStride = uvRowStride ~/ uvWidth;

    final imglib.Image img = imglib.Image(width: width, height: height);

    for (int y = 0; y < height; y++) {
      final int uvRow = uvRowStride * (y ~/ 2);
      for (int x = 0; x < width; x++) {
        final int uvOffset = uvRow + (x ~/ 2) * uvPixelStride;
        final int yp =
            image.planes[0].bytes[y * image.planes[0].bytesPerRow + x];
        final int up = image.planes[1].bytes[uvOffset];
        final int vp = image.planes[2].bytes[uvOffset];

        int r = (yp + (1.370705 * (vp - 128))).round();
        int g =
            (yp - (0.698001 * (vp - 128)) - (0.337633 * (up - 128))).round();
        int b = (yp + (1.732446 * (up - 128))).round();

        r = r.clamp(0, 255);
        g = g.clamp(0, 255);
        b = b.clamp(0, 255);

        img.setPixel(x, y, imglib.ColorRgb8(r, g, b));
      }
    }

    return Uint8List.fromList(imglib.encodeJpg(img, quality: 90));
  }

  Future<void> _startFaceMesh() async {
    await _methodChannel.invokeMethod('startFaceMesh');
    _eventSubscription = _eventChannel.receiveBroadcastStream().listen((data) {
      if (data is Uint8List) {
        setState(() {
          _processedImageBytes = data;
        });
      }
    });
  }

  Future<void> _stopFaceMesh() async {
    await _methodChannel.invokeMethod('stopFaceMesh');
    _eventSubscription?.cancel();
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    _stopFaceMesh();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Always show the live camera preview
          if (_cameraController != null &&
              _cameraController!.value.isInitialized)
            CameraPreview(_cameraController!),
          // Overlay the processed image if available
          if (_processedImageBytes != null)
            Image.memory(
              _processedImageBytes!,
              fit: BoxFit.cover,
              // Optionally add opacity or blending so the preview remains visible.
              color: Colors.white.withValues(alpha: 0.8),
              colorBlendMode: BlendMode.modulate,
            ),
        ],
      ),
    );
  }
}
