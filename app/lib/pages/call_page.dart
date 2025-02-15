import 'dart:async';
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image/image.dart' as img;

import '../helpers/face_detection_service.dart';
import '../helpers/nv21_to_rgb.dart';
import '../widgets/main_feed.dart';
import '../widgets/pip_preview.dart';
import '../widgets/subtitles_display.dart';
import '../widgets/call_controls.dart';

class CallPage extends StatefulWidget {
  final String username;
  const CallPage({Key? key, required this.username}) : super(key: key);

  @override
  State<CallPage> createState() => _CallPageState();
}

class _CallPageState extends State<CallPage> with WidgetsBindingObserver {
  CameraController? _cameraController;
  List<CameraDescription>? cameras;
  bool isCameraInitialized = false;
  int selectedCameraIndex = 1;
  bool isCameraOn = true;
  String subtitles = "Live subtitles will appear here.";
  Rect? mouthBoundingBox;
  bool _isProcessingFrame = false;
  img.Image? _image;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    FaceDetectionService.loadModel();
    _initializeCamera();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final CameraController? cameraController = _cameraController;
    if (cameraController == null || !cameraController.value.isInitialized) {
      return;
    }
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      cameraController.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _initializeCameraController(selectedCameraIndex);
    }
  }

  Future<void> _initializeCamera() async {
    try {
      WidgetsFlutterBinding.ensureInitialized();
      cameras = await availableCameras();
      print(cameras);
      if (cameras != null && cameras!.isNotEmpty) {
        _initializeCameraController(selectedCameraIndex);
      }
    } catch (e) {
      print('Error initializing camera: $e');
    }
  }

  Future<void> _initializeCameraController(int cameraIndex) async {
    if (!isCameraOn) return;
    try {
      final camera = cameras![cameraIndex];
      _cameraController = CameraController(
        camera,
        ResolutionPreset.medium,
        imageFormatGroup: ImageFormatGroup.nv21,
        fps: 15,
      );
      await _cameraController!.initialize();
      // Start image stream for processing.
      await _cameraController!.startImageStream(_processCameraFrameStream);
      setState(() {
        isCameraInitialized = true;
      });
    } catch (e) {
      print('Error initializing camera controller: $e');
    }
  }

  void _flipCamera() async {
    if (cameras != null && cameras!.length > 1) {
      if (cameras!.length <= 2) {
        return;
      }
      await _cameraController?.stopImageStream();
      await _cameraController?.dispose();
      _cameraController = null;
      selectedCameraIndex = (selectedCameraIndex + 1) % cameras!.length;
      print(selectedCameraIndex);
      _initializeCameraController(selectedCameraIndex);
    }
  }

  void _toggleCamera() {
    if (isCameraOn) {
      _cameraController?.stopImageStream();
      _cameraController?.dispose();
      _cameraController = null;
      setState(() {
        isCameraOn = false;
        isCameraInitialized = false;
      });
    } else {
      setState(() {
        isCameraOn = true;
      });
      _initializeCameraController(selectedCameraIndex);
    }
  }

  // This function demonstrates how you might process the camera frame.
  // (Currently not used since _cameraImageToBytes is called from startImageStream.)
  void _processCameraFrameStream(CameraImage image) async {
    if (_isProcessingFrame) return;
    _isProcessingFrame = true;

    final WriteBuffer allBytes = WriteBuffer();
    for (final Plane plane in image.planes) {
      allBytes.putUint8List(plane.bytes);
    }
    final bytes = allBytes.done().buffer.asUint8List();

    final rect = await FaceDetectionService.detectMouth(
        bytes, image.width, image.height);
    setState(() {
      mouthBoundingBox = rect;
    });
    _isProcessingFrame = false;
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Main Feed: Full-screen image view.
          MainFeed(
            cameraController: _cameraController,
            mouthBoundingBox: mouthBoundingBox,
          ),
          // (Optional) Draw the mouth bounding box overlay.
          if (mouthBoundingBox != null)
            Positioned(
              left: mouthBoundingBox!.left,
              top: mouthBoundingBox!.top,
              child: Container(
                width: mouthBoundingBox!.width,
                height: mouthBoundingBox!.height,
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.red, width: 2),
                ),
              ),
            ),
          // Picture-in-Picture preview.
          PipPreview(
            isCameraInitialized: isCameraInitialized,
            cameraController: _cameraController,
            cameras: cameras,
            selectedCameraIndex: selectedCameraIndex,
            isCameraOn: isCameraOn,
          ),
          // Subtitles overlay.
          SubtitlesDisplay(
            subtitles: subtitles,
          ),
          // Call Controls.
          CallControls(
            onFlipCamera: _flipCamera,
            onToggleCamera: _toggleCamera,
            onEndCall: () {
              Navigator.pop(context);
            },
            isCameraOn: isCameraOn,
          ),
        ],
      ),
    );
  }
}
