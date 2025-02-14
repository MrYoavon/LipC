// package com.example.lip_c

// import android.content.Context
// import android.graphics.Bitmap
// import android.graphics.Rect
// import com.google.mediapipe.solutions.facemesh.FaceMesh
// import com.google.mediapipe.solutions.facemesh.FaceMeshOptions
// import com.google.mediapipe.solutions.facemesh.FaceMeshResult

// class FaceMeshDetector(
//     context: Context,
//     private val resultCallback: (Bitmap?) -> Unit
// ) {
//     private val faceMesh: FaceMesh
//     private var currentFrame: Bitmap? = null

//     @Volatile
//     private var isProcessing = false

//     init {
//         val options = FaceMeshOptions.builder()
//             .setStaticImageMode(false)  // implies live stream mode when false
//             .setRefineLandmarks(true)
//             .setMaxNumFaces(1)
//             .build()
//         faceMesh = FaceMesh(context, options)

//         faceMesh.setResultListener { result: FaceMeshResult ->
//             val croppedBitmap = cropMouthRegion(result)
//             resultCallback(croppedBitmap)
//             // Reset the flag to allow the next frame.
//             isProcessing = false
//         }
//     }

//     // Call this with each new frame (a Bitmap) from Flutter.
//     fun processFrame(bitmap: Bitmap, timestamp: Long) {
//         if (isProcessing) return
//         currentFrame = bitmap  // Save the current frame
//         isProcessing = true
//         faceMesh.send(bitmap, timestamp)
//     }

//     // Simple crop logic using a few representative mouth landmarks.
//     private fun cropMouthRegion(result: FaceMeshResult): Bitmap? {
//         val originalBitmap = currentFrame ?: return null  // Use the stored frame
//         if (result.multiFaceLandmarks().isEmpty()) return null
//         val landmarks = result.multiFaceLandmarks()[0].landmarkList

//         // Example indices for lips (adjust as needed)
//         val mouthIndices = listOf(61, 185, 40, 39, 37, 0, 267, 269, 270, 409,
//                                    146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
//                                    78, 191, 80, 81, 82, 13, 312, 311, 310, 415,
//                                    95, 88, 178, 87, 14, 317, 402, 318, 324, 308)
//         var minX = Float.MAX_VALUE
//         var minY = Float.MAX_VALUE
//         var maxX = 0f
//         var maxY = 0f

//         for (index in mouthIndices) {
//             if (index < landmarks.size) {
//                 val lm = landmarks[index]
//                 if (lm.x < minX) minX = lm.x
//                 if (lm.y < minY) minY = lm.y
//                 if (lm.x > maxX) maxX = lm.x
//                 if (lm.y > maxY) maxY = lm.y
//             }
//         }

//         val width = originalBitmap.width
//         val height = originalBitmap.height
//         val left = (minX * width).toInt()
//         val top = (minY * height).toInt()
//         val right = (maxX * width).toInt()
//         val bottom = (maxY * height).toInt()

//         // Add optional padding
//         val padding = 20
//         val cropRect = Rect(
//             (left - padding).coerceAtLeast(0),
//             (top - padding).coerceAtLeast(0),
//             (right + padding).coerceAtMost(width),
//             (bottom + padding).coerceAtMost(height)
//         )
//         return Bitmap.createBitmap(originalBitmap,
//             cropRect.left,
//             cropRect.top,
//             cropRect.width(),
//             cropRect.height()
//         )
//     }

//     fun release() {
//         faceMesh.close()
//     }
// }
