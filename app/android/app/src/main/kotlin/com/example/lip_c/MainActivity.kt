package com.example.lip_c

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.os.Bundle
import androidx.annotation.NonNull
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.ByteArrayOutputStream

class MainActivity: FlutterActivity() {
    // Ensure the channel name here matches the one on the Flutter side.
    private val CHANNEL = "com.example.lip_c/yuv"

    override fun configureFlutterEngine(@NonNull flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "convertNV21ToRGB" -> {
                        val nv21Data = call.argument<ByteArray>("data")
                        val width = call.argument<Int>("width")
                        val height = call.argument<Int>("height")
                        if (nv21Data == null || width == null || height == null) {
                            result.error("INVALID_ARGS", "Missing one or more arguments", null)
                            return@setMethodCallHandler
                        }
                        try {
                            // Call the updated conversion that returns raw RGB data.
                            val rgbRaw = convertNV21ToRGBRaw(nv21Data, width, height)
                            result.success(rgbRaw)
                        } catch (e: Exception) {
                            result.error("CONVERSION_ERROR", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /**
     * Converts an NV21 (YUV) byte array into a raw RGB byte array.
     *
     * The conversion is done by using YuvImage to compress the NV21 data to JPEG,
     * then decoding it into a Bitmap, and finally extracting the raw RGB pixel values.
     *
     * @param nv21Data The NV21 data.
     * @param width The width of the image.
     * @param height The height of the image.
     * @return A byte array of length (width * height * 3) containing the raw RGB data.
     */
    private fun convertNV21ToRGBRaw(nv21Data: ByteArray, width: Int, height: Int): ByteArray {
        // Create a YuvImage from the NV21 data.
        val yuvImage = YuvImage(nv21Data, ImageFormat.NV21, width, height, null)
        val jpegOutputStream = ByteArrayOutputStream()
        // Compress the YuvImage to JPEG. (Quality of 100 to minimize artifacts.)
        if (!yuvImage.compressToJpeg(Rect(0, 0, width, height), 100, jpegOutputStream)) {
            throw Exception("YuvImage compression failed")
        }
        val jpegBytes = jpegOutputStream.toByteArray()
        // Decode the JPEG bytes into a Bitmap.
        val bitmap: Bitmap = BitmapFactory.decodeByteArray(jpegBytes, 0, jpegBytes.size)
            ?: throw Exception("Bitmap decoding failed")
        // Ensure the Bitmap is in ARGB_8888 format.
        val argbBitmap = bitmap.copy(Bitmap.Config.ARGB_8888, false)

        // Create an int array to hold pixel data.
        val pixels = IntArray(width * height)
        argbBitmap.getPixels(pixels, 0, width, 0, 0, width, height)

        // Allocate a byte array for raw RGB data.
        val rgbBytes = ByteArray(width * height * 3)
        // Convert each pixel from ARGB to RGB.
        for (i in pixels.indices) {
            val pixel = pixels[i]
            val r = (pixel shr 16) and 0xff
            val g = (pixel shr 8) and 0xff
            val b = pixel and 0xff
            rgbBytes[i * 3] = r.toByte()
            rgbBytes[i * 3 + 1] = g.toByte()
            rgbBytes[i * 3 + 2] = b.toByte()
        }
        return rgbBytes
    }
}
