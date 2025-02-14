// package com.example.lip_c

// import android.graphics.Bitmap
// import android.graphics.BitmapFactory
// import android.os.Bundle
// import io.flutter.embedding.android.FlutterActivity
// import io.flutter.embedding.engine.FlutterEngine
// import io.flutter.plugin.common.EventChannel
// import io.flutter.plugin.common.MethodChannel
// import java.io.ByteArrayOutputStream
// import java.nio.ByteBuffer
// import android.graphics.ImageFormat
// import android.graphics.YuvImage
// import android.media.Image
// import android.renderscript.*

// class MainActivity : FlutterActivity() {
//     private val METHOD_CHANNEL = "com.example.lip_c/face_mesh"
//     private val EVENT_CHANNEL = "com.example.lip_c/face_mesh/events"
//     private var faceMeshDetector: FaceMeshDetector? = null
//     private var eventSink: EventChannel.EventSink? = null

//     override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
//         super.configureFlutterEngine(flutterEngine)

//         MethodChannel(flutterEngine.dartExecutor.binaryMessenger, METHOD_CHANNEL)
//             .setMethodCallHandler { call, result ->
//                 when (call.method) {
//                     "startFaceMesh" -> {
//                         startFaceMesh()
//                         result.success(null)
//                     }
//                     "stopFaceMesh" -> {
//                         stopFaceMesh()
//                         result.success(null)
//                     }
//                     "sendFrame" -> {
//                         val frameBytes = call.arguments as? ByteArray
//                         if (frameBytes != null) {
//                             processFrame(frameBytes)
//                             result.success(null)
//                         } else {
//                             result.error("INVALID_ARGUMENT", "Frame bytes not provided", null)
//                         }
//                     }
//                     else -> result.notImplemented()
//                 }
//             }

//         EventChannel(flutterEngine.dartExecutor.binaryMessenger, EVENT_CHANNEL)
//             .setStreamHandler(object : EventChannel.StreamHandler {
//                 override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
//                     eventSink = events
//                 }
//                 override fun onCancel(arguments: Any?) {
//                     eventSink = null
//                 }
//             })
//     }

//     private fun startFaceMesh() {
//         faceMeshDetector = FaceMeshDetector(this) { processedBitmap ->
//             processedBitmap?.let {
//                 val stream = ByteArrayOutputStream()
//                 it.compress(Bitmap.CompressFormat.JPEG, 90, stream)
//                 val bytes = stream.toByteArray()
//                 runOnUiThread {
//                     eventSink?.success(bytes)
//                 }
//             }
//         }
//     }

//     private fun stopFaceMesh() {
//         faceMeshDetector?.release()
//         faceMeshDetector = null
//     }

//     private fun processFrame(frameBytes: ByteArray) {
//         val bitmap = BitmapFactory.decodeByteArray(frameBytes, 0, frameBytes.size)
//         bitmap?.let {
//             faceMeshDetector?.processFrame(it, System.currentTimeMillis())
//         }
//     }
// }