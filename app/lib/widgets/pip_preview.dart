import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

class PipPreview extends StatelessWidget {
  final bool isCameraInitialized;
  final CameraController? cameraController;
  final List<CameraDescription>? cameras;
  final int selectedCameraIndex;
  final bool isCameraOn;
  const PipPreview({
    Key? key,
    required this.isCameraInitialized,
    required this.cameraController,
    required this.cameras,
    required this.selectedCameraIndex,
    required this.isCameraOn,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Positioned(
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
          child: isCameraInitialized && cameraController != null
              ? RotatedBox(
                  quarterTurns: cameras![selectedCameraIndex].lensDirection ==
                          CameraLensDirection.front
                      ? 3
                      : 1,
                  child: CameraPreview(cameraController!),
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
    );
  }
}
