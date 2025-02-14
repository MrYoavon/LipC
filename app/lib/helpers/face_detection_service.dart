import 'dart:typed_data';
import 'package:tflite_flutter/tflite_flutter.dart';
import 'package:flutter/widgets.dart';
import 'package:image/image.dart' as img;

import 'nv21_to_rgb.dart';

class FaceDetectionService {
  static Interpreter? _interpreter;

  // Loads the face detection short range model.
  // This model expects an input image of size 128x128x3.
  static Future<void> loadModel() async {
    _interpreter =
        await Interpreter.fromAsset("assets/face_detection_short_range.tflite");
    print("interpreter: $_interpreter");
  }

  // Runs inference on the provided NV21 image data.
  // It resizes the image to 128x128, normalizes the pixels, and creates the proper input tensor.
  // Then, it runs inference in real time and post-processes the model output to obtain the mouth bounding box.
  static Future<Rect?> detectMouth(Uint8List imageData, int sourceWidth,
      int sourceHeight, int rotationAngle) async {
    if (_interpreter == null) return null;

    // Get expected input shape: [1, targetHeight, targetWidth, channels]
    final inputShape = _interpreter!.getInputTensor(0).shape;
    final targetHeight = inputShape[1];
    final targetWidth = inputShape[2];
    // For our model, we expect 128x128x3.
    // Since the provided image is in NV21 format, we should convert it to RGB.
    Uint8List rgbData = await NV21Converter.convertNV21ToRGB(
        imageData, sourceWidth, sourceHeight);

    // print("Image Data Length: ${rgbData.length}");
    // print("Expected: ${sourceWidth * sourceHeight * 3}");
    // Decode image using package:image.
    img.Image? image = img.Image.fromBytes(
        bytes: rgbData.buffer, width: sourceWidth, height: sourceHeight);
    // print("image: $image");
    if (image == null) {
      print('Failed to decode image');
      return null;
    }

    // Resize image to match model's expected input size.
    img.Image resizedImage =
        img.copyResize(image, width: targetWidth, height: targetHeight);

    // Rotate the image.
    img.Image rotatedImage = img.copyRotate(resizedImage, angle: rotationAngle);

    // Create input tensor: a 4D array of shape [1, targetHeight, targetWidth, channels] with normalized pixel values.
    // Replace the normalization in the input tensor generation:
    var input = List.generate(
      1,
      (_) => List.generate(
          targetHeight,
          (y) => List.generate(targetWidth, (x) {
                final pixel = rotatedImage.getPixel(x, y);
                // Extract RGB components and normalize to [-1.0, 1.0].
                double r = (pixel.r / 127.5) - 1.0;
                double g = (pixel.g / 127.5) - 1.0;
                double b = (pixel.b / 127.5) - 1.0;
                return [r, g, b];
              }, growable: false),
          growable: false),
      growable: false,
    );
    // print(
    //     "input shape: ${input.length}x${input[0].length}x${input[0][0].length}x${input[0][0][0].length}");

    Map<int, Object> outputs = {
      0: List.filled(1 * 896 * 16, 0).reshape([1, 896, 16]), // Regressors
      1: List.filled(1 * 896 * 1, 0).reshape([1, 896, 1]), // Classificators
    };

    // Run inference.
    _interpreter!.runForMultipleInputs([input], outputs);

    // Post-process the output.
    // print(outputs);
    final mouthBox = getMouthBox(outputs);
    print(mouthBox);

    return mouthBox;
  }
}

List<int> getShape(dynamic list) {
  List<int> shape = [];
  while (list is List) {
    shape.add(list.length);
    if (list.isNotEmpty) {
      list = list.first;
    } else {
      break;
    }
  }
  return shape;
}

// Recursively creates a multi-dimensional list (tensor) filled with 0.0 based on the provided shape.
dynamic createTensor(List<int> shape) {
  if (shape.length == 1) {
    return List.filled(shape[0], 0.0);
  }
  return List.generate(shape[0], (_) => createTensor(shape.sublist(1)));
}

// Extracts the mouth bounding box from the model output.
Rect? getMouthBox(Map<int, Object> outputs) {
  /*
    BlazeFace TFLite Model Output Structure (as per the official model card):
    
    For each detected face, the regression output (outputs[0]) contains 16 values:
      [0]  x_center of face
      [1]  y_center of face
      [2]  face width
      [3]  face height
      [4]  left eye x-coordinate
      [5]  left eye y-coordinate
      [6]  right eye x-coordinate
      [7]  right eye y-coordinate
      [8]  nose tip x-coordinate
      [9]  nose tip y-coordinate
      [10] mouth x-coordinate
      [11] mouth y-coordinate
      [12] left eye tragi x-coordinate
      [13] left eye tragi y-coordinate
      [14] right eye tragion x-coordinate
      [15] right eye tragion y-coordinate

    The second output (outputs[1]) contains the detection confidence scores.
    
    In this code we:
      1. Find the anchor with the highest confidence.
      2. Extract the face box and mouth keypoint.
      3. Compute a bounding box around the mouth using a fraction of the face box size.
  */

  // Extract the nested lists properly
  final List<List<List<dynamic>>> rawRegressors =
      outputs[0] as List<List<List<dynamic>>>;
  final List<List<List<dynamic>>> rawClassificators =
      outputs[1] as List<List<List<dynamic>>>;

  // Convert the nested lists into 2D lists
  final List<List<dynamic>> regressors = rawRegressors[0]; // Shape: [896, 16]
  final List<List<dynamic>> classificators =
      rawClassificators[0]; // Shape: [896, 1]

  // Find the index of the highest confidence score
  int maxIndex = 0;
  double maxConfidence = -1;

  for (int i = 0; i < classificators.length; i++) {
    if (classificators[i][0] > maxConfidence) {
      maxConfidence = classificators[i][0];
      maxIndex = i;
    }
  }

  // Extract face bounding box parameters.
  final double faceXCenter = regressors[maxIndex][0]; // x_center of face
  final double faceYCenter = regressors[maxIndex][1]; // y_center of face
  final double faceWidth = regressors[maxIndex][2]; // face width
  final double faceHeight = regressors[maxIndex][3]; // face height
  print("Face: $faceXCenter, $faceYCenter, $faceWidth, $faceHeight");

  // Extract mouth keypoint.
  final double mouthXCenter = regressors[maxIndex][10]; // mouth x
  final double mouthYCenter = regressors[maxIndex][11]; // mouth y
  print("Mouth: $mouthXCenter, $mouthYCenter");

  // Define mouth bounding box size relative to the face box.
  // Adjust these factors based on empirical results.
  final double mouthBoxWidth = faceWidth * 0.4;
  final double mouthBoxHeight = faceHeight * 0.2;

  // Calculate the top-left and bottom-right coordinates.
  final double x1 = mouthXCenter - mouthBoxWidth / 2;
  final double y1 = mouthYCenter - mouthBoxHeight / 2;
  final double x2 = mouthXCenter + mouthBoxWidth / 2;
  final double y2 = mouthYCenter + mouthBoxHeight / 2;

  // // Convert normalized coordinates to image scale.
  // final imageWidth = 128; // Change to match your actual image dimensions.
  // final imageHeight = 128; // Change to match your actual image dimensions.

  // return Rect.fromLTRB(
  //   x1 * imageWidth,
  //   y1 * imageHeight,
  //   x2 * imageWidth,
  //   y2 * imageHeight,
  // );
  return Rect.fromLTRB(x1, y1, x2, y2);
}

// A simple class to hold anchor information.
class Anchor {
  final double xCenter;
  final double yCenter;
  final double width;
  final double height;

  Anchor(this.xCenter, this.yCenter, this.width, this.height);
}
