import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

class MainFeed extends StatelessWidget {
  final CameraController? cameraController;
  final Rect? mouthBoundingBox;

  const MainFeed({
    Key? key,
    required this.cameraController,
    this.mouthBoundingBox,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: cameraController != null && cameraController!.value.isInitialized
          ? Stack(
              fit: StackFit.expand,
              children: [
                RotatedBox(
                  quarterTurns: 3,
                  child: CameraPreview(cameraController!),
                ),
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
              ],
            )
          : const Center(child: CircularProgressIndicator()),
    );
  }
}
