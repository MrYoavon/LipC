// import 'dart:typed_data';

// import 'package:tflite/tflite.dart';

// class LipReadingService {
//   static Future<void> loadModel() async {
//     try {
//       String? result = await Tflite.loadModel(
//         model: "assets/final_model.tflite", // Path to the .tflite file
//       );
//       print("Model loaded: $result");
//     } catch (e) {
//       print("Failed to load the model: $e");
//     }
//   }

//   static Future<String?> predict(List<Uint8List> inputData) async {
//     try {
//       var output = await Tflite.runModelOnFrame(
//         bytesList: inputData, // Input video frame as bytes
//         imageHeight: 50, // Set according to model input shape
//         imageWidth: 125,
//         numResults: 1,
//         threshold: 0.1,
//         asynch: true,
//       );

//       if (output != null && output.isNotEmpty) {
//         return output[0]["label"]; // Return the predicted label
//       }
//     } catch (e) {
//       print("Failed to run inference: $e");
//     }
//     return null;
//   }

//   static Future<void> dispose() async {
//     await Tflite.close();
//   }
// }
