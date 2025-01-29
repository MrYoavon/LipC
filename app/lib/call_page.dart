import 'package:flutter/material.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:camera/camera.dart';

class CallPage extends StatefulWidget {
  final String username;

  const CallPage({super.key, required this.username});

  @override
  State<CallPage> createState() => _CallPageState();
}

class _CallPageState extends State<CallPage> {
  CameraController? _cameraController; // Controller for the camera
  List<CameraDescription>? cameras; // List of cameras available
  bool isCameraInitialized = false;
  int selectedCameraIndex = 0; // Index of the currently active camera
  bool isCameraOn = true; // Tracks if the camera is currently on

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    try {
      // Fetch available cameras
      cameras = await availableCameras();

      // Initialize the selected camera
      if (cameras != null && cameras!.isNotEmpty) {
        _initializeCameraController(selectedCameraIndex);
      }
    } catch (e) {
      print('Error initializing camera: $e');
    }
  }

  Future<void> _initializeCameraController(int cameraIndex) async {
    if (!isCameraOn) return; // Don't initialize if the camera is off

    try {
      final camera = cameras![cameraIndex];
      _cameraController = CameraController(
        camera,
        ResolutionPreset.medium, // Set desired resolution
      );

      // Initialize the camera controller
      await _cameraController!.initialize();

      // Update state once initialized
      setState(() {
        isCameraInitialized = true;
      });
    } catch (e) {
      print('Error initializing camera controller: $e');
    }
  }

  void _flipCamera() {
    if (cameras != null && cameras!.length > 1) {
      // Toggle between front and back cameras
      selectedCameraIndex = (selectedCameraIndex + 1) % cameras!.length;
      _initializeCameraController(selectedCameraIndex);
    }
  }

  void _toggleCamera() {
    if (isCameraOn) {
      // Turn off the camera
      _cameraController?.dispose();
      setState(() {
        isCameraOn = false;
        isCameraInitialized = false;
      });
    } else {
      // Turn on the camera
      setState(() {
        isCameraOn = true;
      });
      _initializeCameraController(selectedCameraIndex);
    }
  }

  @override
  void dispose() {
    // Dispose of the camera controller when done
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Main Video Feed
          Positioned.fill(
            bottom: 10,
            child: Container(
              decoration: const BoxDecoration(color: Colors.black),
              child: Center(
                child: AspectRatio(
                  aspectRatio: 9 / 16, // Set the feed to vertical orientation
                  child: Container(
                    color: Colors.grey
                        .shade800, // Placeholder for the other person's video
                    child: Center(
                      child: Text(
                        '${widget.username}\'s Video',
                        style:
                            const TextStyle(color: Colors.white, fontSize: 16),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),

          // Self Video (Picture-in-Picture)
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
                        quarterTurns: cameras![selectedCameraIndex]
                                    .lensDirection ==
                                CameraLensDirection.front
                            ? 7 // Rotate 270 degrees for front camera (was upside down) - 3 is 270 but 7 is 270 with horizontal flip
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
                            child: Text("Camera off"),
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
                color: Colors.black.withAlpha(153), // 60% transparency
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Text(
                'Live subtitles will appear here.',
                style: TextStyle(color: Colors.white, fontSize: 16),
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

                // Mute/Unmute
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
                        : const Icon(
                            LucideIcons.videoOff,
                            color: Colors.white,
                          ),
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
