import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:lucide_icons/lucide_icons.dart';

import 'helpers/face_detection_service.dart';

class CallPage extends StatefulWidget {
  final String username;
  const CallPage({super.key, required this.username});

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
    // If the controller is null or not initialized, there's nothing to do.
    if (cameraController == null || !cameraController.value.isInitialized) {
      return;
    }

    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      // Dispose the camera when the app goes to the background.
      cameraController.dispose();
    } else if (state == AppLifecycleState.resumed) {
      // Reinitialize the camera when the app comes back to the foreground.
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
        ResolutionPreset.low,
        imageFormatGroup: ImageFormatGroup.nv21,
      );
      await _cameraController!.initialize();
      // Start image stream for real-time processing.
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
      // Stop current stream and dispose current controller.
      if (cameras!.length <= 2) {
        return;
      }
      await _cameraController?.stopImageStream();
      await _cameraController?.dispose();
      _cameraController = null;
      // Switch camera index.
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

  void _processCameraFrameStream(CameraImage image) async {
    if (_isProcessingFrame) return;
    _isProcessingFrame = true;

    // try {
    // Convert CameraImage to Uint8List.
    final WriteBuffer allBytes = WriteBuffer();
    for (final Plane plane in image.planes) {
      allBytes.putUint8List(plane.bytes);
    }
    final bytes = allBytes.done().buffer.asUint8List();

    // Use the actual resolution of the image.
    final rotationAngle = cameras![selectedCameraIndex].lensDirection ==
            CameraLensDirection.front
        ? 270 // Rotate 270 degrees for front camera (was upside down) - 3 is 270 but 7 is 270 with horizontal flip
        : 90; // Rotate 90 degrees for rear camera (was sideways)
    final rect = await FaceDetectionService.detectMouth(
        bytes, image.width, image.height, rotationAngle);
    setState(() {
      mouthBoundingBox = rect;
    });
    // } catch (e) {
    //   print('Error processing frame: $e');
    // } finally {
    //   _isProcessingFrame = false;
    // }
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
          // Main Feed: Show processed (cropped if available, else original) image.
          Positioned.fill(
            // bottom: 10,
            // child: Center(
            child: (_cameraController != null &&
                    _cameraController!.value.isInitialized
                ? RotatedBox(
                    quarterTurns: cameras![selectedCameraIndex].lensDirection ==
                            CameraLensDirection.front
                        ? 3
                        : 1,
                    child: CameraPreview(_cameraController!))
                : const CircularProgressIndicator()),
          ),
          // ),
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

          // Picture-in-Picture: Show original camera preview.
          Positioned(
            top: 40,
            right: 20,
            child: Container(
              width: 120,
              height: 160,
              decoration: BoxDecoration(
                color: Colors.grey.shade700,
                borderRadius: BorderRadius.circular(12),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: isCameraInitialized && _cameraController != null
                    ? RotatedBox(
                        // quarterTurns: 0,
                        quarterTurns: cameras![selectedCameraIndex]
                                    .lensDirection ==
                                CameraLensDirection.front
                            ? 3 // Rotate 270 degrees for front camera (was upside down) - 3 is 270 but 7 is 270 with horizontal flip
                            : 1, // Rotate 90 degrees for rear camera (was sideways)
                        child: CameraPreview(_cameraController!),
                      )
                    : isCameraOn
                        ? const Center(
                            child: CircularProgressIndicator(
                              color: Colors.white,
                            ),
                          )
                        : const Center(
                            child: Text("Camera off",
                                style: TextStyle(color: Colors.white)),
                          ),
              ),
            ),
          ),

          // Subtitles
          Positioned(
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
          ),

          // Call Controls
          Positioned(
            bottom: 30,
            left: 20,
            right: 20,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                // Flip Camera
                CircleAvatar(
                  radius: 28,
                  backgroundColor: Colors.grey.shade800,
                  child: IconButton(
                    icon:
                        const Icon(LucideIcons.refreshCw, color: Colors.white),
                    onPressed: _flipCamera,
                  ),
                ),
                // Mute/Unmute (dummy)
                CircleAvatar(
                  radius: 28,
                  backgroundColor: Colors.grey.shade800,
                  child: IconButton(
                    icon: const Icon(LucideIcons.mic, color: Colors.white),
                    onPressed: () {},
                  ),
                ),
                // Toggle Video
                CircleAvatar(
                  radius: 28,
                  backgroundColor:
                      isCameraOn ? Colors.white : Colors.grey.shade800,
                  child: IconButton(
                    icon: isCameraOn
                        ? Icon(LucideIcons.video, color: Colors.grey.shade800)
                        : const Icon(LucideIcons.videoOff, color: Colors.white),
                    onPressed: _toggleCamera,
                  ),
                ),
                // End Call
                CircleAvatar(
                  radius: 28,
                  backgroundColor: Colors.red,
                  child: IconButton(
                    icon: const Icon(LucideIcons.phoneOff, color: Colors.white),
                    onPressed: () {
                      Navigator.pop(context);
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
